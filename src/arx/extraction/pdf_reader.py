"""Text-layer extraction for digitally-generated PDFs, via pdfplumber."""

from __future__ import annotations

import re
from typing import List

import pdfplumber

from arx.extraction.models import PageContent

# Threshold used to decide whether a PDF has a usable text layer at all, vs.
# being a scan that needs OCR. Counted over a sample of pages.
_MIN_CHARS_PER_PAGE_FOR_TEXT_PDF = 40


def load_pdf_text(path: str) -> List[PageContent]:
    """Extract text + ruled tables from every page of a text-based PDF."""
    pages: List[PageContent] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            # layout=True preserves the original character spacing (padding
            # gaps with spaces based on x-position) instead of collapsing
            # runs of whitespace to a single space. Most Indian annual
            # reports align statement columns with whitespace rather than
            # ruling lines, so this is what makes the "\s{2,}" column-split
            # fallback in arx.parse.rows actually work.
            text = page.extract_text(layout=True) or page.extract_text() or ""
            try:
                tables = page.extract_tables() or []
            except Exception:
                # pdfplumber's table finder occasionally chokes on unusual
                # ruling-line geometry; degrade to text-only for this page
                # rather than failing the whole document.
                tables = []
            raw_rows = [re.split(r"\s{2,}", ln.strip()) for ln in text.splitlines() if ln.strip()]
            pages.append(
                PageContent(page_number=i, text=text, tables=tables, raw_rows=raw_rows, is_ocr=False)
            )
    return pages


def page_count(path: str) -> int:
    with pdfplumber.open(path) as pdf:
        return len(pdf.pages)


def has_text_layer(path: str, sample_pages: int = 8) -> bool:
    """Heuristic: does this PDF have a real text layer, or is it a scan?

    Samples up to ``sample_pages`` pages spread across the document (scanned
    front-matter/cover pages sometimes carry a little embedded text even in
    an otherwise-scanned report, so checking only the first page can give a
    false positive).
    """
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        if n == 0:
            return False
        step = max(1, n // sample_pages)
        indices = list(range(0, n, step))[:sample_pages]
        total_chars = 0
        for i in indices:
            text = pdf.pages[i].extract_text() or ""
            total_chars += len(text.strip())
        avg_chars = total_chars / max(1, len(indices))
        return avg_chars >= _MIN_CHARS_PER_PAGE_FOR_TEXT_PDF
