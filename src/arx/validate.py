"""Automated footing and cross-footing checks on extracted statements.

This is the accuracy backstop. OCR errors on financial statements are
rarely obvious -- a misread digit produces a perfectly plausible-looking
number, and no amount of staring at the output will reveal it. But
financial statements are internally redundant: revenue plus other income
must equal total income, assets must equal equity plus liabilities,
operating plus investing plus financing cash flows must equal the net
movement in cash. If an extracted figure is wrong, these identities stop
holding.

So rather than asking the analyst to tie out every number by hand, each
identity that can be tested from the extracted data is tested, and any
break is reported with the size of the discrepancy.

A check is only run when every input it needs was actually extracted;
missing inputs produce a "skipped" result, never a false alarm.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

# A check passes if the difference is within either tolerance -- relative
# for large figures, absolute for small ones (and for rounding in the
# source document itself, which commonly differs by a unit or two).
RELATIVE_TOLERANCE = 0.005
ABSOLUTE_TOLERANCE = 1.0


@dataclass(frozen=True)
class Identity:
    """``target`` should equal the sum of ``components`` (minus ``subtract``)."""

    statement: str
    description: str
    target: str
    components: List[str]
    subtract: List[str] = None  # type: ignore[assignment]
    # Line items whose presence means this identity doesn't apply. A P&L
    # that reports exceptional items separately breaks the simple
    # "income - expenses = profit before tax" chain, and reporting that as
    # a failure would be a false alarm -- which is expensive, because a
    # validation tool people stop trusting is worse than no validation.
    skip_if_present: List[str] = None  # type: ignore[assignment]

    def inputs(self) -> List[str]:
        return [self.target] + list(self.components) + list(self.subtract or [])


IDENTITIES: List[Identity] = [
    # --- Statement of Profit and Loss ---
    Identity(
        "profit_and_loss", "Revenue + Other Income = Total Income",
        target="Total Income",
        components=["Revenue from Operations", "Other Income"],
    ),
    Identity(
        "profit_and_loss", "Total Income - Total Expenses = Profit Before Exceptional Items",
        target="Profit Before Exceptional Items and Tax",
        components=["Total Income"], subtract=["Total Expenses"],
    ),
    Identity(
        "profit_and_loss", "Total Income - Total Expenses = Profit Before Tax",
        target="Profit Before Tax",
        components=["Total Income"], subtract=["Total Expenses"],
        # Only valid when there's no separate pre-exceptional subtotal; if
        # there is, the chain runs through it and via exceptional items.
        skip_if_present=["Profit Before Exceptional Items and Tax"],
    ),
    Identity(
        "profit_and_loss", "Profit Before Exceptional Items - Exceptional Items = PBT",
        target="Profit Before Tax",
        components=["Profit Before Exceptional Items and Tax"], subtract=["Exceptional Items"],
    ),
    Identity(
        "profit_and_loss", "PBT - Current Tax - Deferred Tax = Profit for the Year",
        target="Profit for the Year",
        components=["Profit Before Tax"], subtract=["Current Tax", "Deferred Tax"],
    ),
    # --- Balance Sheet ---
    Identity(
        "balance_sheet", "Total Assets = Total Equity and Liabilities",
        target="Total Assets", components=["Total Equity and Liabilities"],
    ),
    Identity(
        "balance_sheet", "Current + Non-Current Assets = Total Assets",
        target="Total Assets",
        components=["Total Current Assets", "Total Non-Current Assets"],
    ),
    Identity(
        "balance_sheet", "Equity + Non-Current + Current Liabilities = Total Equity and Liabilities",
        target="Total Equity and Liabilities",
        components=["Total Equity", "Total Non-Current Liabilities", "Total Current Liabilities"],
    ),
    Identity(
        "balance_sheet", "Share Capital + Other Equity = Total Equity",
        target="Total Equity",
        components=["Equity Share Capital", "Other Equity"],
    ),
    # --- Cash Flow Statement ---
    Identity(
        "cash_flow", "Operating + Investing + Financing = Net Change in Cash",
        target="Net Increase/(Decrease) in Cash",
        components=[
            "Net Cash from Operating Activities",
            "Net Cash from Investing Activities",
            "Net Cash from Financing Activities",
        ],
    ),
    Identity(
        "cash_flow", "Opening Cash + Net Change = Closing Cash",
        target="Cash and Cash Equivalents at End of Year",
        components=[
            "Cash and Cash Equivalents at Beginning of Year",
            "Net Increase/(Decrease) in Cash",
        ],
    ),
]


def _within_tolerance(expected: float, actual: float) -> bool:
    diff = abs(expected - actual)
    if diff <= ABSOLUTE_TOLERANCE:
        return True
    scale = max(abs(expected), abs(actual))
    return scale > 0 and (diff / scale) <= RELATIVE_TOLERANCE


def run_checks(historical: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Run every applicable identity check over a historical table set.

    ``historical`` maps statement key -> DataFrame indexed by line item
    with one column per fiscal year.
    """
    rows: List[dict] = []

    for identity in IDENTITIES:
        table = historical.get(identity.statement)
        if table is None or table.empty:
            continue

        blockers = [
            name for name in (identity.skip_if_present or [])
            if name in table.index
        ]

        for fiscal_year in table.columns:
            if any(pd.notna(table.at[name, fiscal_year]) for name in blockers):
                continue

            values: Dict[str, Optional[float]] = {}
            for name in identity.inputs():
                if name in table.index:
                    val = table.at[name, fiscal_year]
                    values[name] = None if pd.isna(val) else float(val)
                else:
                    values[name] = None

            if any(values[name] is None for name in identity.inputs()):
                missing = [n for n in identity.inputs() if values[n] is None]
                rows.append({
                    "statement": identity.statement,
                    "fiscal_year": fiscal_year,
                    "check": identity.description,
                    "expected": None,
                    "extracted": None,
                    "difference": None,
                    "status": "skipped",
                    "detail": f"not extracted: {', '.join(missing)}",
                })
                continue

            expected = sum(values[c] for c in identity.components)
            expected -= sum(values[s] for s in (identity.subtract or []))
            actual = values[identity.target]
            ok = _within_tolerance(expected, actual)
            rows.append({
                "statement": identity.statement,
                "fiscal_year": fiscal_year,
                "check": identity.description,
                "expected": round(expected, 2),
                "extracted": round(actual, 2),
                "difference": round(actual - expected, 2),
                "status": "PASS" if ok else "FAIL",
                "detail": "" if ok else "extracted figure does not foot -- verify against source",
            })

    columns = ["statement", "fiscal_year", "check", "expected", "extracted",
               "difference", "status", "detail"]
    return pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame(columns=columns)


def summarize(checks: pd.DataFrame) -> str:
    if checks.empty:
        return "No checks could be run."
    counts = checks["status"].value_counts().to_dict()
    return (
        f"{counts.get('PASS', 0)} passed, "
        f"{counts.get('FAIL', 0)} failed, "
        f"{counts.get('skipped', 0)} skipped"
    )
