"""Process many statement PDFs at once and consolidate them into a
multi-year historical series.

The typical input is what an analyst actually has on disk: a folder of
per-statement, per-year exports --

    2022-23 Balance Sheet.pdf     2024-25 Balancesheet.pdf
    2022-2023 Income Statement.pdf    2024-25 Income Statement.pdf
    2022-23 Cash Flow.pdf         2024-25 Cash flow.pdf

Filenames like these carry two useful facts: which statement the file
contains, and which fiscal year it's for. Using them removes all guesswork
from statement location, and gives a fallback way to date the columns when
the page header can't be read.

The consolidation rule that matters: a value is only placed into a dated
historical column when its column mapping is *known*, not assumed. Rows
whose column count doesn't match the detected header, and files whose
headers couldn't be read confidently, are reported for review instead of
being quietly folded into the series.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from arx.extraction.models import PageContent
from arx.extraction.ocr import ocr_image_file, ocr_pdf_pages
from arx.extraction.pdf_reader import has_text_layer, load_pdf_text
from arx.locate.statement_finder import find_statement_pages
from arx.parse.columns import ColumnLayout, detect_period_columns
from arx.parse.table_parser import build_statement_dataframe
from arx.pipeline import IMAGE_EXTENSIONS
from arx.standardize.mapper import standardize
from arx.standardize.schema import SCHEMAS, STATEMENT_DISPLAY_NAMES

_FILENAME_STATEMENT_PATTERNS: Dict[str, List[str]] = {
    "balance_sheet": [r"balance\s*sheet", r"\bbs\b"],
    "profit_and_loss": [r"income\s*statement", r"profit\s*(?:and|&)?\s*loss",
                        r"\bp\s*&\s*l\b", r"\bpnl\b", r"\bp&l\b"],
    "cash_flow": [r"cash\s*flow"],
}

# "2024-25", "2022-2023", "FY2024-25", "2024_25"
_FILENAME_FY_RE = re.compile(r"(?:fy)?\s*(20\d{2})\s*[-_/]\s*(\d{2}|\d{4})", re.IGNORECASE)


def infer_statement_from_filename(path: str) -> Optional[str]:
    name = os.path.basename(path).lower()
    for statement, patterns in _FILENAME_STATEMENT_PATTERNS.items():
        if any(re.search(p, name) for p in patterns):
            return statement
    return None


def infer_fiscal_year_from_filename(path: str) -> Optional[str]:
    match = _FILENAME_FY_RE.search(os.path.basename(path))
    if not match:
        return None
    start = int(match.group(1))
    return f"FY{start}-{str(start + 1)[-2:]}"


def previous_fiscal_year(fy_label: str) -> Optional[str]:
    m = re.match(r"FY(\d{4})-(\d{2})", fy_label)
    if not m:
        return None
    start = int(m.group(1)) - 1
    return f"FY{start}-{str(start + 1)[-2:]}"


@dataclass
class FileResult:
    path: str
    statement: Optional[str]
    fiscal_year_hint: Optional[str]
    layout: ColumnLayout
    standardized: pd.DataFrame
    unmapped: pd.DataFrame
    raw: pd.DataFrame
    used_ocr: bool
    pages_used: List[int] = field(default_factory=list)
    note: str = ""

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)


def _load_pages(path: str, force_ocr: bool, dpi: int) -> tuple:
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return ocr_image_file(path), True
    if ext != ".pdf":
        raise ValueError(f"Unsupported file type: {ext}")
    if not force_ocr and has_text_layer(path):
        return load_pdf_text(path), False
    return ocr_pdf_pages(path, dpi=dpi), True


def process_file(path: str, force_ocr: bool = False, dpi: int = 300) -> List[FileResult]:
    """Extract every statement present in one file.

    A per-statement export yields one result; a full annual report can
    yield up to three.
    """
    pages, used_ocr = _load_pages(path, force_ocr, dpi)
    fy_hint = infer_fiscal_year_from_filename(path)
    hinted_statement = infer_statement_from_filename(path)

    if hinted_statement:
        # The filename says this whole file is one statement, so skip page
        # location entirely and read every page -- more reliable than
        # keyword scoring, especially on noisy OCR text.
        statement_pages = {hinted_statement: [p.page_number for p in pages]}
        note = f"statement taken from filename ({hinted_statement})"
    else:
        statement_pages = find_statement_pages(pages)
        note = "statement located by page scoring"

    results: List[FileResult] = []
    for statement, page_numbers in statement_pages.items():
        if not page_numbers:
            continue
        raw = build_statement_dataframe(pages, page_numbers)
        if raw.empty:
            continue
        mapping = standardize(raw, statement)
        layout = _detect_layout(pages, page_numbers)
        results.append(FileResult(
            path=path,
            statement=statement,
            fiscal_year_hint=fy_hint,
            layout=layout,
            standardized=mapping.standardized,
            unmapped=mapping.unmapped,
            raw=raw,
            used_ocr=used_ocr,
            pages_used=page_numbers,
            note=note,
        ))
    return results


def _detect_layout(pages: List[PageContent], page_numbers: List[int]) -> ColumnLayout:
    """Read column headers from the first page of the statement."""
    wanted = [p for p in pages if p.page_number in set(page_numbers)]
    best = ColumnLayout(confident=False, note="no pages available")
    for page in wanted:
        layout = detect_period_columns(page.text)
        if layout.confident:
            return layout
        if not best.columns and layout.columns:
            best = layout
    return best


@dataclass
class HistoricalResult:
    tables: Dict[str, pd.DataFrame]
    sources: pd.DataFrame
    conflicts: pd.DataFrame
    needs_review: pd.DataFrame
    unmapped: pd.DataFrame


def _fy_sort_key(label: str) -> int:
    m = re.match(r"FY(\d{4})", label)
    return int(m.group(1)) if m else 0


def build_historical(
    file_results: List[FileResult],
    basis_preference: Optional[str] = "consolidated",
) -> HistoricalResult:
    """Merge per-file extractions into one line-item x fiscal-year table
    per statement."""
    # (statement, line_item, fy) -> list of (value, source description)
    collected: Dict[str, Dict[str, Dict[str, List[tuple]]]] = {}
    source_rows: List[dict] = []
    review_rows: List[dict] = []
    unmapped_rows: List[dict] = []

    for result in file_results:
        statement = result.statement
        if statement is None:
            continue
        value_cols = [c for c in result.standardized.columns if c.startswith("value_")]
        n_cols = len(result.layout.columns) if result.layout.columns else len(value_cols)

        target_columns: List[tuple] = []  # (value_col_name, fy_label, basis, confidence)
        if result.layout.confident:
            for column in result.layout.year_columns(basis_preference):
                if column.index < len(value_cols):
                    target_columns.append(
                        (value_cols[column.index], column.fy_label, column.basis, "header")
                    )
        elif not result.layout.is_quarterly_filing and result.fiscal_year_hint:
            # A plain annual statement with an unreadable header: the
            # near-universal layout is [current year, prior year], and the
            # filename tells us the current year.
            if value_cols:
                target_columns.append((value_cols[0], result.fiscal_year_hint, None, "assumed"))
            prior = previous_fiscal_year(result.fiscal_year_hint)
            if len(value_cols) > 1 and prior:
                target_columns.append((value_cols[1], prior, None, "assumed"))

        source_rows.append({
            "file": result.filename,
            "statement": STATEMENT_DISPLAY_NAMES.get(statement, statement),
            "fiscal_year_from_filename": result.fiscal_year_hint,
            "pages_used": ", ".join(str(p) for p in result.pages_used),
            "read_via": "OCR" if result.used_ocr else "text layer",
            "columns_detected": len(result.layout.columns),
            "columns_confident": result.layout.confident,
            "quarterly_filing": result.layout.is_quarterly_filing,
            "years_taken": ", ".join(
                f"{fy} ({basis or 'n/a'}, {conf})" for _, fy, basis, conf in target_columns
            ) or "none",
            "note": result.layout.note,
        })

        if not target_columns:
            review_rows.append({
                "file": result.filename,
                "statement": STATEMENT_DISPLAY_NAMES.get(statement, statement),
                "line_item": "(entire file)",
                "issue": "could not date the columns confidently -- not merged into historicals",
                "detail": result.layout.note,
            })

        for _, row in result.standardized.iterrows():
            n_values = row.get("n_values")
            aligned = pd.notna(n_values) and int(n_values) == n_cols
            for value_col, fy_label, basis, confidence in target_columns:
                value = row.get(value_col)
                if pd.isna(value):
                    continue
                if not aligned:
                    review_rows.append({
                        "file": result.filename,
                        "statement": STATEMENT_DISPLAY_NAMES.get(statement, statement),
                        "line_item": row["line_item"],
                        "issue": "column alignment uncertain -- excluded from historicals",
                        "detail": (
                            f"row parsed {int(n_values) if pd.notna(n_values) else 0} values "
                            f"but the statement has {n_cols} columns"
                        ),
                    })
                    break
                source = f"{result.filename} [{value_col}, {basis or 'n/a'}, {confidence}]"
                (collected
                 .setdefault(statement, {})
                 .setdefault(row["line_item"], {})
                 .setdefault(fy_label, [])
                 .append((float(value), source)))

        for _, row in result.unmapped.iterrows():
            unmapped_rows.append({
                "file": result.filename,
                "statement": STATEMENT_DISPLAY_NAMES.get(statement, statement),
                "raw_label": row["raw_label"],
                "reason": row.get("reason"),
            })

    # --- assemble tables, recording disagreements between files ---
    tables: Dict[str, pd.DataFrame] = {}
    conflict_rows: List[dict] = []

    for statement, items in collected.items():
        years = sorted(
            {fy for per_item in items.values() for fy in per_item},
            key=_fy_sort_key,
        )
        schema_order = [item.label for item in SCHEMAS[statement]]
        ordered_items = [label for label in schema_order if label in items]
        ordered_items += [label for label in items if label not in schema_order]

        data = []
        for label in ordered_items:
            record = {}
            for fy in years:
                entries = items[label].get(fy, [])
                if not entries:
                    record[fy] = None
                    continue
                value = entries[0][0]
                record[fy] = value
                for other_value, other_source in entries[1:]:
                    if abs(other_value - value) > max(1.0, abs(value) * 0.005):
                        conflict_rows.append({
                            "statement": STATEMENT_DISPLAY_NAMES.get(statement, statement),
                            "line_item": label,
                            "fiscal_year": fy,
                            "value_used": value,
                            "value_from_other_file": other_value,
                            "difference": round(other_value - value, 2),
                            "source_used": entries[0][1],
                            "other_source": other_source,
                        })
            data.append(record)

        table = pd.DataFrame(data, index=ordered_items, columns=years)
        table.index.name = "Line Item"
        tables[statement] = table

    return HistoricalResult(
        tables=tables,
        sources=pd.DataFrame(source_rows) if source_rows else pd.DataFrame(),
        conflicts=pd.DataFrame(conflict_rows) if conflict_rows else pd.DataFrame(),
        needs_review=pd.DataFrame(review_rows) if review_rows else pd.DataFrame(),
        unmapped=pd.DataFrame(unmapped_rows) if unmapped_rows else pd.DataFrame(),
    )
