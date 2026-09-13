from arx.parse.rows import split_row, split_text_line


def test_split_row_basic():
    label, values = split_row(["Revenue from operations", "12,345.67", "10,987.65"])
    assert label == "Revenue from operations"
    assert values == [12345.67, 10987.65]


def test_split_row_with_note_ref():
    label, values = split_row(["Trade receivables", "(Note 12)", "5,000.00", "4,500.00"])
    assert label == "Trade receivables"
    assert values == [5000.0, 4500.0]


def test_split_row_negative_paren():
    label, values = split_row(["Finance costs", "(120.00)", "(95.00)"])
    assert label == "Finance costs"
    assert values == [-120.0, -95.0]


def test_split_row_all_blank_returns_none():
    assert split_row(["", None, ""]) is None


def test_split_row_no_values_returns_none():
    assert split_row(["ASSETS", ""]) is None


def test_split_text_line_whitespace_aligned():
    line = "Total Equity and Liabilities        45,678.90        41,234.10"
    label, values = split_text_line(line)
    assert label == "Total Equity and Liabilities"
    assert values == [45678.90, 41234.10]
