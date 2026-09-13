"""Shared data structures used across the extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class PageContent:
    """Everything the pipeline needs from a single page of the source file.

    Attributes:
        page_number: 1-indexed page number in the source document.
        text: Plain text of the page (from the text layer, or OCR).
        tables: Tables detected by pdfplumber's ruling-line based table
            finder. Each table is a list of rows, each row a list of cell
            strings (cells may be None/empty).
        raw_rows: A whitespace-split fallback view of the page as rows of
            string tokens, used when no ruled tables are detected (very
            common in Indian annual reports, which often lay out financial
            statements with whitespace alignment rather than visible grid
            lines).
        is_ocr: True if this page's text came from OCR rather than a PDF
            text layer.
    """

    page_number: int
    text: str
    tables: List[List[List[str]]] = field(default_factory=list)
    raw_rows: List[List[str]] = field(default_factory=list)
    is_ocr: bool = False
