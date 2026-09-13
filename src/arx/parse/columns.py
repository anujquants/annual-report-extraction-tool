"""Work out what each numeric column in a statement actually represents.

This is the difference between a usable historical series and a silently
wrong one. A SEBI quarterly-results filing puts ten number columns side by
side -- three quarters and two full years, for standalone and then
consolidated -- so blindly taking the first column would drop a *quarter*
figure into an annual model. A plain annual-report statement, by contrast,
has two columns (current year, prior year).

Both cases are read off the header rows:

    STANDALONE                                    CONSOLIDATED
    Quarter ended Quarter ended Quarter ended Year ended Year ended  ...
    31.03.2026    31.12.2025    31.03.2025    31.03.2026 31.03.2025  ...

If the header can't be read confidently, that is reported rather than
guessed at -- callers are expected to refuse to merge unconfident columns
into a historical series.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# 31.03.2026 / 31-03-2026 / 31/03/2026. The day is captured but not
# validated -- OCR routinely turns "31" into "32" and the day is irrelevant
# to working out the fiscal year anyway.
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b")
# 31-Mar-2025 / 31 March 2025
_DMY_NAME_RE = re.compile(r"\b(\d{1,2})[\s.-]*([a-z]{3,9})[\s.,-]*(\d{4})\b", re.IGNORECASE)
# March 31, 2026
_MDY_NAME_RE = re.compile(r"\b([a-z]{3,9})[\s.]*(\d{1,2})[\s,]+(\d{4})\b", re.IGNORECASE)

_PERIOD_KIND_RE = re.compile(r"\b(year|quarter|period)\s*ended\b", re.IGNORECASE)


def fiscal_year_label(month: int, year: int) -> str:
    """Map a period-end date to an Indian fiscal year label.

    31 March 2026 -> "FY2025-26" (the year ending in March 2026).
    A period ending after March is treated as belonging to the fiscal year
    that started that calendar year.
    """
    start = year - 1 if month <= 6 else year
    return f"FY{start}-{str(start + 1)[-2:]}"


def _parse_dates_in_line(line: str) -> List[Tuple[int, int]]:
    """Return [(month, year), ...] for every date-looking token in a line."""
    found: List[Tuple[int, int, int]] = []  # (position, month, year)

    for m in _NUMERIC_DATE_RE.finditer(line):
        _, month, year = m.groups()
        month_i = int(month)
        if 1 <= month_i <= 12:
            found.append((m.start(), month_i, int(year)))

    for m in _DMY_NAME_RE.finditer(line):
        _, name, year = m.groups()
        month_i = _MONTHS.get(name[:3].lower())
        if month_i:
            found.append((m.start(), month_i, int(year)))

    for m in _MDY_NAME_RE.finditer(line):
        name, _, year = m.groups()
        month_i = _MONTHS.get(name[:3].lower())
        if month_i:
            found.append((m.start(), month_i, int(year)))

    # De-duplicate overlapping matches from the different patterns, keeping
    # left-to-right order.
    found.sort(key=lambda t: t[0])
    result: List[Tuple[int, int]] = []
    last_pos = -1
    for pos, month, year in found:
        if pos <= last_pos:
            continue
        result.append((month, year))
        last_pos = pos
    return result


@dataclass
class PeriodColumn:
    """One numeric column of a statement."""

    index: int                      # 0-based position among the value columns
    kind: str                       # "year" | "quarter" | "unknown"
    month: Optional[int] = None
    year: Optional[int] = None
    basis: Optional[str] = None     # "standalone" | "consolidated" | None

    @property
    def fy_label(self) -> Optional[str]:
        if self.month is None or self.year is None:
            return None
        return fiscal_year_label(self.month, self.year)

    def describe(self) -> str:
        parts = [self.kind]
        if self.fy_label:
            parts.append(self.fy_label)
        if self.basis:
            parts.append(self.basis)
        return " / ".join(parts)


@dataclass
class ColumnLayout:
    columns: List[PeriodColumn] = field(default_factory=list)
    confident: bool = False
    is_quarterly_filing: bool = False
    note: str = ""

    def year_columns(self, basis_preference: Optional[str] = None) -> List[PeriodColumn]:
        """Year-end columns only, optionally restricted to one reporting basis.

        Falls back to the other basis if the preferred one isn't present, so
        a standalone-only filing still yields its annual columns.
        """
        years = [c for c in self.columns if c.kind == "year" and c.fy_label]
        if not years:
            return []
        if basis_preference:
            preferred = [c for c in years if c.basis == basis_preference]
            if preferred:
                return preferred
            unbased = [c for c in years if c.basis is None]
            if unbased:
                return unbased
        return years


def detect_period_columns(text: str) -> ColumnLayout:
    """Read the header rows of a statement page and describe its columns."""
    lines = [ln for ln in text.splitlines() if ln.strip()]

    kinds: List[str] = []
    kinds_line_idx: Optional[int] = None
    for i, line in enumerate(lines):
        matches = _PERIOD_KIND_RE.findall(line)
        if len(matches) >= 2:
            kinds = ["year" if m.lower() == "year" else "quarter" for m in matches]
            kinds_line_idx = i
            break

    # Dates: prefer a line at or just after the kinds line, else the first
    # line anywhere with two or more dates.
    dates: List[Tuple[int, int]] = []
    search_order = range(len(lines))
    if kinds_line_idx is not None:
        search_order = list(range(kinds_line_idx, min(kinds_line_idx + 4, len(lines)))) + list(
            range(len(lines))
        )
    for i in search_order:
        candidate = _parse_dates_in_line(lines[i])
        if len(candidate) >= 2:
            dates = candidate
            break

    lowered = text.lower()
    has_standalone = "standalone" in lowered
    has_consolidated = "consolidated" in lowered

    # --- Case 1: an explicit "Quarter ended / Year ended" header row ---
    if kinds:
        bases: List[Optional[str]] = [None] * len(kinds)
        half = len(kinds) // 2
        # The standard filing repeats the same period pattern for standalone
        # then consolidated. A sequence that is exactly doubled is strong
        # evidence of where the split falls -- much more reliable than trying
        # to use the x-position of the words in OCR'd text.
        if (
            has_standalone
            and has_consolidated
            and len(kinds) % 2 == 0
            and kinds[:half] == kinds[half:]
        ):
            bases = ["standalone"] * half + ["consolidated"] * half
        elif has_consolidated and not has_standalone:
            bases = ["consolidated"] * len(kinds)
        elif has_standalone and not has_consolidated:
            bases = ["standalone"] * len(kinds)

        if len(dates) == len(kinds):
            columns = [
                PeriodColumn(index=i, kind=kinds[i], month=dates[i][0], year=dates[i][1],
                             basis=bases[i])
                for i in range(len(kinds))
            ]
            return ColumnLayout(
                columns=columns,
                confident=True,
                is_quarterly_filing="quarter" in kinds,
                note=f"Matched {len(kinds)} period headers to {len(dates)} dates.",
            )

        columns = [PeriodColumn(index=i, kind=kinds[i], basis=bases[i]) for i in range(len(kinds))]
        return ColumnLayout(
            columns=columns,
            confident=False,
            is_quarterly_filing="quarter" in kinds,
            note=(
                f"Found {len(kinds)} period headers but {len(dates)} dates -- "
                "columns could not be dated confidently."
            ),
        )

    # --- Case 2: a plain annual statement, e.g. "As at 31-Mar-2025  31-Mar-2024" ---
    if dates:
        basis = None
        if has_consolidated and not has_standalone:
            basis = "consolidated"
        elif has_standalone and not has_consolidated:
            basis = "standalone"
        columns = [
            PeriodColumn(index=i, kind="year", month=m, year=y, basis=basis)
            for i, (m, y) in enumerate(dates)
        ]
        return ColumnLayout(
            columns=columns,
            confident=True,
            is_quarterly_filing=False,
            note=f"No quarter/year header row; treated {len(dates)} dated columns as annual.",
        )

    return ColumnLayout(confident=False, note="No period header row or dates found.")
