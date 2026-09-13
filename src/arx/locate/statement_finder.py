"""Locate which pages of an annual report contain the standalone/consolidated
financial statements (Balance Sheet, Statement of Profit & Loss, Cash Flow
Statement).

Annual reports mention "profit", "assets" etc. constantly in the
Directors' Report and MD&A sections, so a plain keyword search over-selects.
We score each page on two things:

1. Title-like keyword hits (e.g. the page literally says "Balance Sheet as
   at ...", "Statement of Profit and Loss", "Cash Flow Statement").
2. Line-item density -- how many of the well-known Schedule III line items
   for that statement appear on the page. A real statement page is packed
   with these; a prose page that happens to mention "profit" once is not.

Pages are then selected as a contiguous-ish block around the
highest-scoring page(s), since a statement often spans 1-3 pages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

from arx.extraction.models import PageContent

_TITLE_PATTERNS: Dict[str, List[str]] = {
    "balance_sheet": [
        r"balance\s+sheet\s+as\s+at",
        r"\bbalance\s+sheet\b",
    ],
    "profit_and_loss": [
        r"statement\s+of\s+profit\s+and\s+loss",
        r"profit\s+&\s+loss\s+account",
        r"\bstatement\s+of\s+profit\b",
    ],
    "cash_flow": [
        r"cash\s+flow\s+statement",
        r"statement\s+of\s+cash\s+flow",
    ],
}

_LINE_ITEM_PATTERNS: Dict[str, List[str]] = {
    "balance_sheet": [
        r"equity\s+and\s+liabilit",
        r"property,?\s+plant\s+and\s+equipment",
        r"trade\s+receivabl",
        r"trade\s+payabl",
        r"cash\s+and\s+cash\s+equivalent",
        r"total\s+assets",
        r"share\s+capital",
        r"inventor",
        r"other\s+equity",
    ],
    "profit_and_loss": [
        r"revenue\s+from\s+operations",
        r"other\s+income",
        r"total\s+income",
        r"employee\s+benefit",
        r"finance\s+cost",
        r"depreciation\s+and\s+amortisation",
        r"profit\s+before\s+tax",
        r"tax\s+expense",
        r"earnings\s+per\s+equity\s+share",
        r"profit\s+for\s+the\s+year",
    ],
    "cash_flow": [
        r"cash\s+flow\s+from\s+operating",
        r"cash\s+used\s+in\s+investing",
        r"cash\s+from\s+financing",
        r"net\s+increase.*cash",
        r"cash\s+and\s+cash\s+equivalents\s+at\s+the\s+end",
        r"operating\s+activities",
        r"investing\s+activities",
        r"financing\s+activities",
    ],
}


@dataclass
class PageScore:
    page_number: int
    title_hits: int
    line_item_hits: int

    @property
    def score(self) -> float:
        # A title hit is a strong signal; line-item density backs it up and
        # lets us pull in continuation pages that repeat no title.
        return self.title_hits * 5 + self.line_item_hits


def _score_pages(pages: List[PageContent], statement: str) -> List[PageScore]:
    title_res = [re.compile(p, re.IGNORECASE) for p in _TITLE_PATTERNS[statement]]
    item_res = [re.compile(p, re.IGNORECASE) for p in _LINE_ITEM_PATTERNS[statement]]
    scores = []
    for page in pages:
        text = page.text or ""
        title_hits = sum(1 for r in title_res if r.search(text))
        line_item_hits = sum(1 for r in item_res if r.search(text))
        scores.append(PageScore(page.page_number, title_hits, line_item_hits))
    return scores


def find_statement_pages(
    pages: List[PageContent], min_line_items: int = 3, max_pages_per_statement: int = 4
) -> Dict[str, List[int]]:
    """Return {statement_key: [page_numbers]} for each of the three statements.

    A statement's pages are chosen by: find the best-scoring page (must clear
    a minimum line-item density so we don't latch onto a random prose
    mention), then extend forward while neighbouring pages still show
    meaningful line-item density (statements commonly spread over 2-3 pages),
    up to ``max_pages_per_statement``.
    """
    result: Dict[str, List[int]] = {}
    for statement in _TITLE_PATTERNS:
        scores = _score_pages(pages, statement)
        candidates = [s for s in scores if s.line_item_hits >= min_line_items or s.title_hits > 0]
        if not candidates:
            result[statement] = []
            continue
        best = max(candidates, key=lambda s: s.score)
        by_page = {s.page_number: s for s in scores}
        chosen = [best.page_number]
        # extend forward
        p = best.page_number + 1
        while len(chosen) < max_pages_per_statement:
            s = by_page.get(p)
            if s is None or s.line_item_hits < max(1, min_line_items - 1):
                break
            chosen.append(p)
            p += 1
        result[statement] = chosen
    return result
