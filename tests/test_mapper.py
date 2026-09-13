import pandas as pd

from arx.standardize.mapper import normalize_label, standardize


def test_normalize_label():
    assert normalize_label("  Trade Receivables (Note 12)  ") == "trade receivables note 12"


def _df(rows):
    return pd.DataFrame(rows, columns=["raw_label", "value_1", "value_2", "page"])


def test_standardize_balance_sheet_maps_known_items_in_schema_order():
    df = _df(
        [
            # deliberately out of order to check the output re-orders by schema
            ("Total Assets", 1000.0, 900.0, 5),
            ("Equity Share Capital", 100.0, 100.0, 4),
            ("Cash and cash equivalents", 50.0, 40.0, 5),
            ("Trade receivables", 200.0, 180.0, 5),
        ]
    )
    result = standardize(df, "balance_sheet")
    assert list(result.standardized["line_item"]) == [
        "Total Assets",
        "Equity Share Capital",
        "Trade Receivables",
        "Cash and Cash Equivalents",
    ]
    assert result.unmapped.empty


def test_standardize_keeps_unmatched_rows_as_unmapped():
    df = _df([("Some Weird Company-Specific Line", 42.0, None, 3)])
    result = standardize(df, "profit_and_loss")
    assert result.standardized.empty
    assert len(result.unmapped) == 1
    assert result.unmapped.iloc[0]["raw_label"] == "Some Weird Company-Specific Line"


def test_standardize_duplicate_match_keeps_first_and_flags_second():
    df = _df(
        [
            ("Total Income", 1000.0, None, 2),
            ("Total Income", 1100.0, None, 2),  # e.g. repeated on a continuation page
        ]
    )
    result = standardize(df, "profit_and_loss")
    assert len(result.standardized) == 1
    assert result.standardized.iloc[0]["value_1"] == 1000.0
    assert len(result.unmapped) == 1
    assert "duplicate" in result.unmapped.iloc[0]["reason"]


def test_total_assets_not_confused_with_total_current_assets():
    df = _df(
        [
            ("Total current assets", 300.0, None, 5),
            ("Total Assets", 900.0, None, 5),
        ]
    )
    result = standardize(df, "balance_sheet")
    items = dict(zip(result.standardized["line_item"], result.standardized["value_1"]))
    assert items["Total Current Assets"] == 300.0
    assert items["Total Assets"] == 900.0
