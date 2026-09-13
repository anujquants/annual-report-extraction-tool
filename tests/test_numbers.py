import pytest

from arx.parse.numbers import looks_numeric, parse_number


@pytest.mark.parametrize(
    "token,expected",
    [
        ("1,234.56", 1234.56),
        ("12,34,567.89", 1234567.89),  # Indian grouping
        ("(1,234.56)", -1234.56),
        ("(500)", -500.0),
        ("-", None),
        ("–", None),
        ("—", None),
        ("", None),
        ("Rs. 12,000", 12000.0),
        ("₹ 12,000.50", 12000.50),
        ("12.5%", 12.5),
        ("not a number", None),
        ("0", 0.0),
        ("0.00", 0.0),
    ],
)
def test_parse_number(token, expected):
    result = parse_number(token)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    "token,expected",
    [
        ("1,234.56", True),
        ("-", True),
        ("Total Assets", False),
        ("(500)", True),
        ("Revenue from operations", False),
    ],
)
def test_looks_numeric(token, expected):
    assert looks_numeric(token) is expected
