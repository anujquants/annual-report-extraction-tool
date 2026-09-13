from arx.parse.columns import detect_period_columns, fiscal_year_label

QUARTERLY_HEADER = """
STAR CEMENT LIMITED
Statement of Audited Financial Results for the Quarter and Year ended March 31, 2026
STANDALONE CONSOLIDATED
St Quarter ended   Quarter ended Quarter ended Year ended Year ended Quarter ended Quarter ended Quarter ended Year ended Year ended
Nal Particulars 31.03.2026 31.12.2025 31.03.2025 31.03.2026 31.03.2025 31.03.2026 31.12.2025 31.03.2025 31.03.2026   31.03.2025
Revenue from Operations 78,539.54 53,183.28 65,825.84 2,38,363.45 1,99,218.89 1,17,355.11 88,000.34 1,05,208.79 3,77,648.73 3,16,339.49
"""

ANNUAL_HEADER = """
Balance Sheet as at 31-Mar-2025
Particulars                        As at 31-Mar-2025   As at 31-Mar-2024
Property, Plant and Equipment              12,500.00           11,200.00
"""


def test_fiscal_year_label_march_year_end():
    assert fiscal_year_label(3, 2026) == "FY2025-26"
    assert fiscal_year_label(3, 2025) == "FY2024-25"


def test_quarterly_filing_columns_are_identified():
    layout = detect_period_columns(QUARTERLY_HEADER)
    assert layout.confident
    assert layout.is_quarterly_filing
    assert len(layout.columns) == 10
    kinds = [c.kind for c in layout.columns]
    assert kinds == ["quarter"] * 3 + ["year"] * 2 + ["quarter"] * 3 + ["year"] * 2
    bases = [c.basis for c in layout.columns]
    assert bases == ["standalone"] * 5 + ["consolidated"] * 5


def test_consolidated_year_columns_are_selected():
    layout = detect_period_columns(QUARTERLY_HEADER)
    years = layout.year_columns("consolidated")
    # Columns 9 and 10 (0-indexed 8 and 9) are the consolidated annual columns.
    assert [c.index for c in years] == [8, 9]
    assert [c.fy_label for c in years] == ["FY2025-26", "FY2024-25"]


def test_standalone_preference_picks_the_other_half():
    layout = detect_period_columns(QUARTERLY_HEADER)
    years = layout.year_columns("standalone")
    assert [c.index for c in years] == [3, 4]


def test_plain_annual_statement_columns():
    layout = detect_period_columns(ANNUAL_HEADER)
    assert layout.confident
    assert not layout.is_quarterly_filing
    assert [c.kind for c in layout.columns] == ["year", "year"]
    assert [c.fy_label for c in layout.columns] == ["FY2024-25", "FY2023-24"]


def test_no_header_is_reported_as_not_confident():
    layout = detect_period_columns("Some prose with no dates or period headers at all.")
    assert not layout.confident
    assert layout.columns == []
