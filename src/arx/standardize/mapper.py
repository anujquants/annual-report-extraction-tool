"""Map raw extracted row labels onto the canonical schema for a statement.

Design choices, spelled out because they matter for a valuation tool where
silently dropping or double-counting a line item is worse than not mapping
it at all:

- Regex first, in schema-definition order (schema.py orders "total" rows
  before component rows, and longer/more specific phrases before shorter
  ones). First match wins.
- Fuzzy matching only as a fallback, for labels OCR has damaged past
  regex recognition ("Protit/(Loss) before tax", "Deterred Tax"). It is
  deliberately conservative: a high similarity threshold plus a margin
  requirement over the runner-up, so an ambiguous label is left unmapped
  rather than assigned to the wrong line item. Every fuzzy match is
  labelled with its score in the output so it can be audited.
- If a canonical slot is already filled and another raw row also matches
  it, the *first* one is kept and the duplicate is pushed to "unmapped"
  with a note -- rather than silently overwriting (a data integrity issue)
  or silently summing (wrong more often than right).
- Anything that doesn't match is kept in a separate "unmapped" table --
  never dropped -- so you can see what the tool missed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

import pandas as pd

from arx.standardize.schema import SchemaItem, SCHEMAS

_NORMALIZE_RE = re.compile(r"[^a-z0-9\s]")
_WHITESPACE_RE = re.compile(r"\s+")
# A leading sub-item enumeration marker -- "a) Current Tax", "(b) Deferred
# Tax", "13 Paid up Equity Share Capital" -- stripped only when there's
# clearly more label text after it, so a schema pattern like "^current
# tax$" still matches the real line item underneath the marker.
_LEADING_ENUM_RE = re.compile(r"^(?:[a-z]{1,2}|\d{1,3})\s+(?=\S)")

# Tuned against real OCR output: genuine matches on damaged labels score
# 0.80+, while the closest wrong pairings ("total income" vs "total
# expenses") top out around 0.62.
FUZZY_THRESHOLD = 0.78
FUZZY_MARGIN = 0.06


def normalize_label(label: str) -> str:
    s = label.lower()
    s = _NORMALIZE_RE.sub(" ", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    s = _LEADING_ENUM_RE.sub("", s)
    return s


def _window_ratio(label: str, key: str) -> float:
    """Best similarity between ``key`` and any same-length window of ``label``.

    Comparing whole strings would punish the trailing junk OCR leaves on a
    row ("...before tax (3-4) 9,854.48"); comparing windows finds the part
    of the label that actually corresponds to the line item name.
    """
    label_tokens = label.split()
    key_tokens = key.split()
    n = len(key_tokens)
    if not label_tokens or not key_tokens:
        return 0.0
    best = 0.0
    for width in range(max(1, n - 1), n + 3):
        for start in range(0, max(1, len(label_tokens) - width + 1)):
            window = " ".join(label_tokens[start:start + width])
            best = max(best, SequenceMatcher(None, window, key).ratio())
    return best


def _fuzzy_match(normalized: str, schema: List[SchemaItem]) -> Tuple[Optional[SchemaItem], float]:
    """Best fuzzy candidate, or (None, score) if it isn't clear enough.

    Candidates are ranked by *specificity first* (number of tokens in the
    key), then score. Ranking by score alone is actively dangerous here: on
    "Profit/(Loss) before exceptionat Items", the two-word key "exceptional
    items" scores 0.94 against a short window while the correct six-word key
    "profit before exceptional items and tax" scores 0.80 -- picking the
    higher score would confidently file a subtotal under the wrong line
    item. This mirrors the most-specific-first ordering the regex patterns
    already rely on.
    """
    scored = [(item, _window_ratio(normalized, item.match_key)) for item in schema]
    candidates = [(item, score) for item, score in scored if score >= FUZZY_THRESHOLD]
    if not candidates:
        best_score = max((s for _, s in scored), default=0.0)
        return None, best_score

    candidates.sort(key=lambda pair: (len(pair[0].match_key.split()), pair[1]), reverse=True)
    best_item, best_score = candidates[0]

    # Ambiguity guard: two equally specific candidates scoring within a
    # hair of each other means we can't tell them apart -- leave the row
    # unmapped rather than guess.
    best_specificity = len(best_item.match_key.split())
    for item, score in candidates[1:]:
        if len(item.match_key.split()) != best_specificity:
            break
        if abs(score - best_score) < FUZZY_MARGIN:
            return None, best_score

    return best_item, best_score


@dataclass
class MappingResult:
    standardized: pd.DataFrame
    unmapped: pd.DataFrame


def _compiled_schema(statement: str):
    return [
        (item, [re.compile(p, re.IGNORECASE) for p in item.patterns])
        for item in SCHEMAS[statement]
    ]


def standardize(df: pd.DataFrame, statement: str, allow_fuzzy: bool = True) -> MappingResult:
    if statement not in SCHEMAS:
        raise ValueError(f"Unknown statement type: {statement}")

    value_cols = [c for c in df.columns if c.startswith("value_")]
    compiled = _compiled_schema(statement)
    schema = SCHEMAS[statement]

    filled: Dict[str, dict] = {}
    unmapped_rows: List[dict] = []

    for _, row in df.iterrows():
        raw_label = row["raw_label"]
        norm = normalize_label(raw_label)
        matched_item: Optional[SchemaItem] = None
        match_quality = "exact"

        for item, patterns in compiled:
            if any(p.search(norm) for p in patterns):
                matched_item = item
                break

        if matched_item is None and allow_fuzzy:
            candidate, score = _fuzzy_match(norm, schema)
            if candidate is not None:
                matched_item = candidate
                match_quality = f"fuzzy ({score:.2f})"

        if matched_item is None:
            unmapped_rows.append({
                "raw_label": raw_label,
                "page": row.get("page"),
                **{c: row[c] for c in value_cols},
                "reason": "no schema match",
            })
            continue

        if matched_item.key in filled:
            unmapped_rows.append({
                "raw_label": raw_label,
                "page": row.get("page"),
                **{c: row[c] for c in value_cols},
                "reason": f"duplicate match for '{matched_item.label}' (first occurrence kept)",
            })
            continue

        filled[matched_item.key] = {
            "line_item": matched_item.label,
            "raw_label": raw_label,
            "match": match_quality,
            "n_values": row.get("n_values"),
            "page": row.get("page"),
            **{c: row[c] for c in value_cols},
        }

    # Emit in schema-declared order so the workbook reads like a real
    # financial statement, not in whatever order rows happened to match.
    ordered_records = [filled[item.key] for item in schema if item.key in filled]

    std_columns = ["line_item", "raw_label", "match", "n_values"] + value_cols + ["page"]
    standardized = (
        pd.DataFrame.from_records(ordered_records, columns=std_columns)
        if ordered_records
        else pd.DataFrame(columns=std_columns)
    )

    unmapped_columns = ["raw_label"] + value_cols + ["page", "reason"]
    unmapped = (
        pd.DataFrame.from_records(unmapped_rows, columns=unmapped_columns)
        if unmapped_rows
        else pd.DataFrame(columns=unmapped_columns)
    )

    return MappingResult(standardized=standardized, unmapped=unmapped)
