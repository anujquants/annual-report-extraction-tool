"""Parsing numeric tokens as they appear in Indian financial statements.

Handles the quirks that trip up a naive ``float(x)``:

- Thousands separators in the Indian numbering system: ``12,34,567.89``
- Parentheses for negative numbers: ``(1,234.56)`` -> ``-1234.56``
- A lone dash/en-dash/em-dash used to mean "nil": ``-``, ``–``, ``—``
- Currency symbols / unit markers: ``Rs.``, ``₹``, ``INR``
- Percent signs on ratio rows: ``12.5%``
"""

from __future__ import annotations

import re
from typing import Optional

_NIL_TOKENS = {"-", "–", "—", "--", "nil", "n.a.", "na", ""}

_CURRENCY_STRIP_RE = re.compile(r"[₹$]|rs\.?|inr", flags=re.IGNORECASE)
_NUMBER_RE = re.compile(r"^\(?-?\d[\d,]*\.?\d*\)?%?$")


def is_nil_token(token: Optional[str]) -> bool:
    """True for an explicit 'nil' placeholder ('-', an en/em-dash, etc.)."""
    if token is None:
        return False
    return token.strip().lower() in _NIL_TOKENS


def looks_numeric(token: str) -> bool:
    """Cheap check for whether a token is (or could be coerced to) a number."""
    if token is None:
        return False
    t = token.strip()
    if t.lower() in _NIL_TOKENS:
        return True
    t = _CURRENCY_STRIP_RE.sub("", t).strip()
    return bool(_NUMBER_RE.match(t))


def parse_number(token: Optional[str]) -> Optional[float]:
    """Parse a single cell/token into a float, or None if it's nil/unparseable.

    Returns None both for genuinely missing values ("-") and for tokens that
    don't parse as numbers at all -- callers that need to distinguish the two
    should call :func:`looks_numeric` first.
    """
    if token is None:
        return None
    t = token.strip()
    if t.lower() in _NIL_TOKENS:
        return None

    negative = False
    if t.startswith("(") and t.endswith(")"):
        negative = True
        t = t[1:-1].strip()

    t = _CURRENCY_STRIP_RE.sub("", t).strip()
    t = t.replace("%", "").strip()
    t = t.replace(",", "")

    if t in ("", "-", "."):
        return None

    try:
        value = float(t)
    except ValueError:
        return None

    return -value if negative else value
