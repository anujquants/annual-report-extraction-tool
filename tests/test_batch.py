import pandas as pd

from arx.batch import (
    FileResult,
    build_historical,
    infer_fiscal_year_from_filename,
    infer_statement_from_filename,
    previous_fiscal_year,
)
from arx.parse.columns import ColumnLayout, PeriodColumn


def test_infer_statement_from_filename():
    assert infer_statement_from_filename("2024-25 Balancesheet.pdf") == "balance_sheet"
    assert infer_statement_from_filename("2022-23 Balance Sheet.pdf") == "balance_sheet"
    assert infer_statement_from_filename("2024-25 Income Statement.pdf") == "profit_and_loss"
    assert infer_statement_from_filename("2022-23 Cash Flow.pdf") == "cash_flow"
    assert infer_statement_from_filename("2024-25 Cash flow.pdf") == "cash_flow"
    assert infer_statement_from_filename("Star Cement AR 2025.pdf") is None


def test_infer_fiscal_year_from_filename():
    assert infer_fiscal_year_from_filename("2024-25 Balancesheet.pdf") == "FY2024-25"
    assert infer_fiscal_year_from_filename("2022-2023 Income Statement.pdf") == "FY2022-23"
    assert infer_fiscal_year_from_filename("no year here.pdf") is None


def test_previous_fiscal_year():
    assert previous_fiscal_year("FY2024-25") == "FY2023-24"
    assert previous_fiscal_year("FY2020-21") == "FY2019-20"


def _annual_layout():
    return ColumnLayout(
        columns=[
            PeriodColumn(index=0, kind="year", month=3, year=2025),
            PeriodColumn(index=1, kind="year", month=3, year=2024),
        ],
        confident=True,
    )


def _file_result(filename, values, n_values=2):
    df = pd.DataFrame([{
        "line_item": "Revenue from Operations",
        "raw_label": "Revenue from operations",
        "match": "exact",
        "n_values": n_values,
        "value_1": values[0],
        "value_2": values[1],
        "page": 1,
    }])
    empty = pd.DataFrame()
    return FileResult(
        path=f"/tmp/{filename}", statement="profit_and_loss",
        fiscal_year_hint="FY2024-25", layout=_annual_layout(),
        standardized=df, unmapped=empty, raw=empty, used_ocr=False, pages_used=[1],
    )


def test_historical_merges_current_and_prior_year_columns():
    result = build_historical([_file_result("2024-25 Income Statement.pdf", (18500.0, 16200.0))])
    table = result.tables["profit_and_loss"]
    assert list(table.columns) == ["FY2023-24", "FY2024-25"]
    assert table.at["Revenue from Operations", "FY2024-25"] == 18500.0
    assert table.at["Revenue from Operations", "FY2023-24"] == 16200.0


def test_agreeing_files_produce_no_conflict():
    files = [
        _file_result("2024-25 Income Statement.pdf", (18500.0, 16200.0)),
        _file_result("2023-24 Income Statement.pdf", (16200.0, 14100.0)),
    ]
    # Second file reports FY2023-24 in its first column; make its layout match.
    files[1].layout = ColumnLayout(
        columns=[
            PeriodColumn(index=0, kind="year", month=3, year=2024),
            PeriodColumn(index=1, kind="year", month=3, year=2023),
        ],
        confident=True,
    )
    result = build_historical(files)
    assert result.conflicts.empty


def test_disagreeing_files_are_flagged_as_conflicts():
    files = [
        _file_result("2024-25 Income Statement.pdf", (18500.0, 16200.0)),
        _file_result("2023-24 Income Statement.pdf", (99999.0, 14100.0)),
    ]
    files[1].layout = ColumnLayout(
        columns=[
            PeriodColumn(index=0, kind="year", month=3, year=2024),
            PeriodColumn(index=1, kind="year", month=3, year=2023),
        ],
        confident=True,
    )
    result = build_historical(files)
    assert len(result.conflicts) == 1
    conflict = result.conflicts.iloc[0]
    assert conflict["fiscal_year"] == "FY2023-24"
    assert {conflict["value_used"], conflict["value_from_other_file"]} == {16200.0, 99999.0}


def test_misaligned_rows_are_excluded_and_flagged():
    # Row claims only 1 parsed value while the statement has 2 columns, so
    # we can't tell which year the number belongs to.
    file_result = _file_result("2024-25 Income Statement.pdf", (18500.0, None), n_values=1)
    result = build_historical([file_result])
    assert result.tables.get("profit_and_loss") is None or result.tables["profit_and_loss"].empty
    assert not result.needs_review.empty
    assert "alignment" in result.needs_review.iloc[0]["issue"]
