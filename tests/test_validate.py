import pandas as pd

from arx.validate import run_checks


def _pl_table(total_income):
    return pd.DataFrame(
        {"FY2024-25": [18500.0, 320.0, total_income]},
        index=["Revenue from Operations", "Other Income", "Total Income"],
    )


def test_footing_check_passes_when_statement_ties_out():
    checks = run_checks({"profit_and_loss": _pl_table(18820.0)})
    row = checks[checks["check"].str.contains("Total Income")].iloc[0]
    assert row["status"] == "PASS"


def test_footing_check_fails_on_a_wrong_figure():
    # An OCR digit error: 18,820 read as 13,820.
    checks = run_checks({"profit_and_loss": _pl_table(13820.0)})
    row = checks[checks["check"].str.contains("Total Income")].iloc[0]
    assert row["status"] == "FAIL"
    assert row["difference"] == -5000.0


def test_check_is_skipped_when_an_input_is_missing():
    table = pd.DataFrame({"FY2024-25": [18500.0]}, index=["Revenue from Operations"])
    checks = run_checks({"profit_and_loss": table})
    statuses = set(checks["status"])
    assert statuses == {"skipped"}


def test_small_rounding_differences_are_tolerated():
    checks = run_checks({"profit_and_loss": _pl_table(18820.5)})
    row = checks[checks["check"].str.contains("Total Income")].iloc[0]
    assert row["status"] == "PASS"


def test_balance_sheet_identity():
    table = pd.DataFrame(
        {"FY2024-25": [20900.0, 20900.0, 6950.0, 13950.0]},
        index=["Total Assets", "Total Equity and Liabilities",
               "Total Current Assets", "Total Non-Current Assets"],
    )
    checks = run_checks({"balance_sheet": table})
    assert set(checks[checks["status"] != "skipped"]["status"]) == {"PASS"}


def test_cash_flow_identity_catches_a_break():
    table = pd.DataFrame(
        {"FY2024-25": [3100.0, -1650.0, -900.0, 999.0]},
        index=["Net Cash from Operating Activities",
               "Net Cash from Investing Activities",
               "Net Cash from Financing Activities",
               "Net Increase/(Decrease) in Cash"],
    )
    checks = run_checks({"cash_flow": table})
    row = checks[checks["check"].str.contains("Net Change")].iloc[0]
    assert row["status"] == "FAIL"
    assert row["expected"] == 550.0
