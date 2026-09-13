"""Turning a raw row of cell/text tokens into (label, [values]).

The same logic is used for:
  * pdfplumber-detected table rows (list of cell strings), and
  * the whitespace-split fallback for pages with no ruled table lines.

Real-world wrinkle this has to handle: pdfplumber's layout-preserving text
extraction approximates each character's column position from font metrics,
so the gap between a label and its first number sometimes collapses to a
single space instead of the many spaces used for visual alignment in the
original PDF -- merging "Net cash generated from operating activities" and
"3,100.00" into one whitespace-split token. Rather than trust cell/token
boundaries alone, each token is scanned for a *trailing* run of one or more
number-shaped substrings, which are peeled off one at a time from the right
end; whatever text remains at the front is the label.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from arx.parse.numbers import is_nil_token, looks_numeric, parse_number

# A trailing "note" reference, e.g. "Trade receivables (Note 12)" or
# "Trade receivables 12" -- stripped so it doesn't pollute the label used
# for standardization matching.
_NOTE_REF_RE = re.compile(r"\s*\(?note\s*[:.]?\s*\d+[a-z]?\)?\s*$", re.IGNORECASE)
_TRAILING_BARE_NUMBER_RE = re.compile(r"\s+\d{1,3}[a-z]?$", re.IGNORECASE)

# A "real" financial figure: comma-grouped (Indian or international grouping,
# with or without a decimal), a plain decimal, or a bare integer of 3+
# digits. Deliberately excludes bare 1-2 digit integers, which are far more
# likely to be a footnote/schedule reference (e.g. "...expenses  8") than a
# monetary value in an annual report. May be wrapped in parentheses
# (negative) and/or followed by a percent sign.
_TRAILING_NUMBER_RE = re.compile(
    # ...optionally followed by stray trailing punctuation, which OCR leaves
    # behind surprisingly often ("39,045.59." at the end of a row).
    r"\(?-?(?:\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+\.\d+|\d{3,})\)?%?[.,;:]?$"
    r"|(?<=\s)[-–—](?=$)"
)


def _peel_trailing_numbers(token: str) -> Tuple[str, List[str]]:
    """Repeatedly strip a trailing number-shaped substring off ``token``.

    Returns (remaining_prefix, [number_strings_in_original_left_to_right_order]).
    """
    values: List[str] = []
    s = token
    while True:
        m = _TRAILING_NUMBER_RE.search(s)
        if not m or m.start() == m.end():
            break
        values.append(m.group())
        s = s[: m.start()].rstrip()
        if not s:
            break
    values.reverse()
    return s, values


def split_row(cells: List[Optional[str]]) -> Optional[Tuple[str, List[Optional[float]]]]:
    """Split a row of raw string cells into (label, values).

    Returns None if the row has no usable label (e.g. a fully blank row, or
    a row that is all numbers with nothing to name it -- these are usually
    stray table artifacts).
    """
    cleaned = [c.strip() if isinstance(c, str) else "" for c in cells]
    cleaned = [c for c in cleaned if c != ""]
    if not cleaned:
        return None

    label_parts: List[str] = []
    values: List[Optional[float]] = []
    seen_number = False

    for cell in cleaned:
        if seen_number:
            # Already past the label -- every remaining cell is value
            # columns. Note the plural: a single whitespace-split cell can
            # still hold several numbers, because the gap between two value
            # columns is often only one space ("2,00,621.13 1,18,266.80
            # 88,487.93"). Parsing the cell as one number would return None
            # and silently blank out several years of data.
            _, peeled = _peel_trailing_numbers(cell)
            if peeled:
                values.extend(parse_number(v) for v in peeled)
            else:
                # A nil marker ("-") or unparseable junk: keep the column
                # slot so later columns stay aligned.
                values.append(parse_number(cell))
            continue

        if label_parts and is_nil_token(cell):
            seen_number = True
            values.append(None)
            continue

        if looks_numeric(cell):
            seen_number = True
            values.append(parse_number(cell))
            continue

        prefix, peeled = _peel_trailing_numbers(cell)
        if peeled:
            seen_number = True
            if prefix:
                label_parts.append(prefix)
            values.extend(parse_number(v) for v in peeled)
        else:
            label_parts.append(cell)

    label = " ".join(label_parts).strip()
    label = _NOTE_REF_RE.sub("", label).strip()
    # A bare trailing note number with no parens/label, e.g. "Inventories 8"
    if not values:
        stripped = _TRAILING_BARE_NUMBER_RE.sub("", label).strip()
        if stripped and stripped != label:
            label = stripped

    if not label:
        return None
    # Require at least one real value; a label with zero numeric cells at
    # all usually means it's a sub-heading, not a line item worth keeping.
    if not values:
        return None

    return label, values


def split_text_line(line: str) -> Optional[Tuple[str, List[Optional[float]]]]:
    """Fallback for pages with no ruled table: split on runs of 2+ spaces."""
    line = line.rstrip()
    if not line.strip():
        return None
    cells = re.split(r"\s{2,}", line.strip())
    return split_row(cells)
