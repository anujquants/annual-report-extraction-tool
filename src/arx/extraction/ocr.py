"""OCR fallback for scanned annual report PDFs and standalone images (JPG/PNG).

Scanned financial statement tables rarely have machine-readable ruling
lines, so we don't attempt structured table detection here -- OCR text is
split into rows the same whitespace-heuristic way as the ruled-table
fallback in :mod:`arx.parse.rows`. OCR is noticeably less reliable than
text-layer extraction (digit confusion, misaligned columns), so results
from this path should be spot-checked against the source page.

Scanned pages are also often rotated 90/180/270 degrees from upright
(a page fed into a scanner sideways or upside-down, or a photo taken at an
angle) -- OCR run on a rotated page doesn't fail loudly, it just produces
confident-looking garbage (individual glyphs that happen to look like other
letters/digits when flipped). :func:`_deskew` uses Tesseract's own
orientation detection to correct this before the real OCR pass.
"""

from __future__ import annotations

import re
from typing import List

import pytesseract
from PIL import Image

from arx.extraction.models import PageContent


def _autorotate(image: Image.Image) -> Image.Image:
    """Detect and correct 90/180/270-degree page rotation before OCR.

    Uses Tesseract's orientation-and-script-detection (OSD) mode, which is
    a fast, separate pass from full OCR. Falls back to the original image
    unchanged if OSD can't get a confident reading (common on a mostly-blank
    or very sparse page) rather than raising -- a wrong guess here would be
    worse than doing nothing.
    """
    try:
        osd = pytesseract.image_to_osd(image, config="--psm 0")
    except pytesseract.TesseractError:
        return image

    match = re.search(r"Rotate:\s*(\d+)", osd)
    if not match:
        return image
    rotation = int(match.group(1))
    if rotation == 0:
        return image
    # PIL rotates counter-clockwise; Tesseract's "Rotate" value is the
    # clockwise correction needed, hence the sign flip.
    return image.rotate(-rotation, expand=True)


def _text_to_page(image: Image.Image, page_number: int) -> PageContent:
    image = _autorotate(image)
    text = pytesseract.image_to_string(image)
    # Table ruling lines (vertical borders between columns) are frequently
    # misread by OCR as a literal "|" character sitting mid-row. Left in
    # place, it breaks the row parser's number-peeling partway through a
    # row. It's never a meaningful character in a financial statement, so
    # it's always safe to drop.
    cleaned_text = text.replace("|", " ")
    raw_rows = [re.split(r"\s{2,}", ln.strip()) for ln in cleaned_text.splitlines() if ln.strip()]
    return PageContent(page_number=page_number, text=cleaned_text, tables=[], raw_rows=raw_rows, is_ocr=True)


def ocr_pdf_pages(path: str, dpi: int = 300) -> List[PageContent]:
    """Rasterize each page of a (scanned) PDF and OCR it."""
    from pdf2image import convert_from_path

    images = convert_from_path(path, dpi=dpi)
    return [_text_to_page(image, i) for i, image in enumerate(images, start=1)]


def ocr_image_file(path: str) -> List[PageContent]:
    """OCR a standalone image file (e.g. a photographed annual report page)."""
    image = Image.open(path)
    return [_text_to_page(image, 1)]
