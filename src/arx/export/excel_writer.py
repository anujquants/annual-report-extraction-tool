"""Write extracted + standardized statements to a formatted Excel workbook.

Layout:
    Summary                - key figures & basic ratios, if enough of the
                              standardized data is present to compute them
    Balance Sheet           - standardized line items
    Balance Sheet (raw)     - everything extracted, before mapping
    Balance Sheet (unmapped)- rows that didn't match the schema
    ... same pattern for Profit and Loss / Cash Flow
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from arx.standardize.schema import STATEMENT_DISPLAY_NAMES

HEADER_FMT = {"bold": True, "bg_color": "#1F3864", "font_color": "white", "border": 1}
NUMBER_FMT = "#,##0.00;(#,##0.00)"
STATEMENT_ORDER = ["balance_sheet", "profit_and_loss", "cash_flow"]

# Short, Excel-safe (<=31 char) sheet name stems -- keeps room for the
# " (raw)" / " (unmapped)" suffixes without truncating mid-word.
SHEET_NAME_STEM = {
    "balance_sheet": "Balance Sheet",
    "profit_and_loss": "P&L",
    "cash_flow": "Cash Flow",
}


def _autosize(worksheet, df: pd.DataFrame, start_col: int = 0):
    for i, col in enumerate(df.columns):
        if len(df):
            series_len = max(len(str(v)) for v in df[col].tolist())
        else:
            series_len = 0
        width = max(len(str(col)), series_len) + 2
        worksheet.set_column(start_col + i, start_col + i, min(max(width, 10), 60))


def _write_df(writer, sheet_name: str, df: pd.DataFrame, number_cols=None):
    workbook = writer.book
    header_fmt = workbook.add_format(HEADER_FMT)
    number_fmt = workbook.add_format({"num_format": NUMBER_FMT})

    df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=1, header=False)
    worksheet = writer.sheets[sheet_name]
    for col_idx, col_name in enumerate(df.columns):
        worksheet.write(0, col_idx, col_name, header_fmt)

    number_cols = number_cols or [c for c in df.columns if str(c).startswith("value_")]
    for col_idx, col_name in enumerate(df.columns):
        if col_name in number_cols:
            worksheet.set_column(col_idx, col_idx, 16, number_fmt)
    _autosize(worksheet, df)
    worksheet.freeze_panes(1, 1)


def _safe_get(df: pd.DataFrame, key: str, value_col: str = "value_1") -> Optional[float]:
    if df is None or df.empty or "line_item" not in df.columns:
        return None
    matches = df[df["line_item"] == key]
    if matches.empty or value_col not in df.columns:
        return None
    val = matches.iloc[0][value_col]
    return None if pd.isna(val) else float(val)


def _build_summary_df(standardized: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    from arx.standardize.schema import SCHEMAS

    label_by_key = {}
    for schema in SCHEMAS.values():
        for item in schema:
            label_by_key[item.key] = item.label

    bs = standardized.get("balance_sheet")
    pl = standardized.get("profit_and_loss")
    cf = standardized.get("cash_flow")

    rows = []

    def add(statement_df, key):
        val = _safe_get(statement_df, label_by_key.get(key, key))
        if val is not None:
            rows.append({"Metric": label_by_key.get(key, key), "Value (latest column)": val})

    for key in ["revenue", "total_income", "profit_before_tax", "net_profit"]:
        add(pl, key)
    for key in ["total_assets", "total_equity", "trade_receivables", "cash_and_equivalents"]:
        add(bs, key)
    for key in ["cash_from_operations", "cash_from_investing", "cash_from_financing"]:
        add(cf, key)

    summary = pd.DataFrame(rows)

    # A couple of headline ratios, only computed when both inputs are present.
    revenue = _safe_get(pl, label_by_key.get("revenue"))
    net_profit = _safe_get(pl, label_by_key.get("net_profit"))
    total_equity = _safe_get(bs, label_by_key.get("total_equity"))
    total_assets = _safe_get(bs, label_by_key.get("total_assets"))

    ratio_rows = []
    if revenue and net_profit is not None:
        ratio_rows.append({"Metric": "Net Profit Margin", "Value (latest column)": round(net_profit / revenue, 4)})
    if total_equity and net_profit is not None:
        ratio_rows.append({"Metric": "Return on Equity (approx.)", "Value (latest column)": round(net_profit / total_equity, 4)})
    if total_assets and net_profit is not None:
        ratio_rows.append({"Metric": "Return on Assets (approx.)", "Value (latest column)": round(net_profit / total_assets, 4)})

    if ratio_rows:
        summary = pd.concat([summary, pd.DataFrame(ratio_rows)], ignore_index=True)

    return summary


def write_workbook(output_path: str, results: dict) -> None:
    """``results`` maps statement key -> {"raw": df, "standardized": df, "unmapped": df}."""
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        standardized_map = {k: v.get("standardized") for k, v in results.items()}
        summary_df = _build_summary_df(standardized_map)
        if not summary_df.empty:
            _write_df(writer, "Summary", summary_df, number_cols=["Value (latest column)"])
        else:
            note = pd.DataFrame({"Note": ["Not enough standardized line items were found to build a summary. "
                                           "Check the per-statement sheets and the *_unmapped sheets."]})
            _write_df(writer, "Summary", note, number_cols=[])

        for key in STATEMENT_ORDER:
            if key not in results:
                continue
            stem = SHEET_NAME_STEM.get(key, STATEMENT_DISPLAY_NAMES.get(key, key)[:20])
            std_df = results[key].get("standardized")
            raw_df = results[key].get("raw")
            unmapped_df = results[key].get("unmapped")

            if std_df is not None and not std_df.empty:
                _write_df(writer, stem, std_df)
            if raw_df is not None and not raw_df.empty:
                _write_df(writer, f"{stem} (raw)", raw_df)
            if unmapped_df is not None and not unmapped_df.empty:
                _write_df(writer, f"{stem} (unmapped)", unmapped_df)


# ---------------------------------------------------------------------------
# Multi-file historical workbook
# ---------------------------------------------------------------------------

HISTORICAL_SHEET_NAMES = {
    "profit_and_loss": "Historical P&L",
    "balance_sheet": "Historical Balance Sheet",
    "cash_flow": "Historical Cash Flow",
}


def _write_indexed_df(writer, sheet_name: str, df: pd.DataFrame):
    """Write a line-item-indexed historical table with the index visible."""
    workbook = writer.book
    header_fmt = workbook.add_format(HEADER_FMT)
    number_fmt = workbook.add_format({"num_format": NUMBER_FMT})
    label_fmt = workbook.add_format({"bold": True})

    out = df.reset_index()
    out.to_excel(writer, sheet_name=sheet_name, index=False, startrow=1, header=False)
    worksheet = writer.sheets[sheet_name]
    for col_idx, col_name in enumerate(out.columns):
        worksheet.write(0, col_idx, str(col_name), header_fmt)
    worksheet.set_column(0, 0, 46, label_fmt)
    if len(out.columns) > 1:
        worksheet.set_column(1, len(out.columns) - 1, 18, number_fmt)
    worksheet.freeze_panes(1, 1)


def write_historical_workbook(output_path: str, historical, checks: pd.DataFrame) -> None:
    """Write the consolidated multi-year workbook.

    ``historical`` is an ``arx.batch.HistoricalResult``.
    """
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        wrote_any = False
        for key in STATEMENT_ORDER:
            table = historical.tables.get(key)
            if table is None or table.empty:
                continue
            _write_indexed_df(writer, HISTORICAL_SHEET_NAMES.get(key, key)[:31], table)
            wrote_any = True

        if not wrote_any:
            _write_df(writer, "Historical", pd.DataFrame({
                "Note": ["No statement columns could be dated confidently. "
                         "See the 'Needs Review' and 'Sources' sheets."]
            }), number_cols=[])

        if checks is not None and not checks.empty:
            _write_df(writer, "Checks", checks,
                      number_cols=["expected", "extracted", "difference"])
        if historical.conflicts is not None and not historical.conflicts.empty:
            _write_df(writer, "Conflicts", historical.conflicts,
                      number_cols=["value_used", "value_from_other_file", "difference"])
        if historical.needs_review is not None and not historical.needs_review.empty:
            _write_df(writer, "Needs Review", historical.needs_review, number_cols=[])
        if historical.sources is not None and not historical.sources.empty:
            _write_df(writer, "Sources", historical.sources, number_cols=[])
        if historical.unmapped is not None and not historical.unmapped.empty:
            _write_df(writer, "Unmapped", historical.unmapped, number_cols=[])
