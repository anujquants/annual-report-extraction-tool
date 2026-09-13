"""Turn the pages identified for a given statement into a tidy DataFrame
of (raw_label, value_1, value_2, ...) rows.

Prefers pdfplumber's ruled-table rows when available (more reliable column
alignment); falls back to whitespace-split text lines otherwise, which is
the common case for Indian annual reports that align numbers with spaces
rather than drawing grid lines.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from arx.extraction.models import PageContent
from arx.parse.rows import split_row


def build_statement_dataframe(pages: List[PageContent], page_numbers: List[int]) -> pd.DataFrame:
    wanted = set(page_numbers)
    relevant = [p for p in pages if p.page_number in wanted]

    rows: List[dict] = []
    max_values = 0

    for page in relevant:
        used_ruled_table = False
        for table in page.tables:
            parsed_any = False
            for raw_row in table:
                parsed = split_row(raw_row)
                if parsed is None:
                    continue
                label, values = parsed
                rows.append({"raw_label": label, "values": values, "page": page.page_number})
                max_values = max(max_values, len(values))
                parsed_any = True
            if parsed_any:
                used_ruled_table = True

        if not used_ruled_table:
            for raw_row in page.raw_rows:
                # page.raw_rows entries are already tokenized on 2+ space
                # gaps (see arx.extraction.pdf_reader) -- split_row consumes
                # that token list directly. Re-joining and re-splitting here
                # would collapse the very whitespace that separates columns.
                parsed = split_row(raw_row) if isinstance(raw_row, list) else None
                if parsed is None:
                    continue
                label, values = parsed
                rows.append({"raw_label": label, "values": values, "page": page.page_number})
                max_values = max(max_values, len(values))

    columns = (
        ["raw_label"] + [f"value_{i+1}" for i in range(max_values)] + ["n_values", "page"]
    )
    if not rows:
        return pd.DataFrame(columns=columns)

    records = []
    for r in rows:
        # n_values records how many column slots this row actually consumed
        # while parsing. A None in value_3 could mean either "nil for that
        # year" or "OCR lost this column", and once it's in the DataFrame
        # the two are indistinguishable -- but only the first keeps the
        # year columns aligned. Downstream code uses this to refuse to
        # place a short row into a dated historical series.
        rec = {"raw_label": r["raw_label"], "page": r["page"], "n_values": len(r["values"])}
        for i in range(max_values):
            rec[f"value_{i+1}"] = r["values"][i] if i < len(r["values"]) else None
        records.append(rec)

    df = pd.DataFrame.from_records(records, columns=columns)
    return df
