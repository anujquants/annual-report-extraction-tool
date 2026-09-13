"""Top-level orchestration: input file -> Excel workbook.

This is the single entry point both the CLI and the Streamlit demo call.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd

from arx.extraction.models import PageContent
from arx.extraction.ocr import ocr_image_file, ocr_pdf_pages
from arx.extraction.pdf_reader import has_text_layer, load_pdf_text
from arx.export.excel_writer import write_workbook
from arx.locate.statement_finder import find_statement_pages
from arx.parse.table_parser import build_statement_dataframe
from arx.standardize.mapper import standardize

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


@dataclass
class StatementSummary:
    pages_found: List[int] = field(default_factory=list)
    rows_extracted: int = 0
    rows_standardized: int = 0
    rows_unmapped: int = 0


@dataclass
class PipelineResult:
    output_path: str
    used_ocr: bool
    page_count: int
    statement_summaries: Dict[str, StatementSummary]
    tables: Dict[str, Dict[str, pd.DataFrame]]


def _load_pages(input_path: str, force_ocr: bool, dpi: int) -> tuple[List[PageContent], bool]:
    ext = os.path.splitext(input_path)[1].lower()

    if ext in IMAGE_EXTENSIONS:
        return ocr_image_file(input_path), True

    if ext != ".pdf":
        raise ValueError(f"Unsupported file type: {ext}. Expected a PDF or an image (jpg/png).")

    if not force_ocr and has_text_layer(input_path):
        return load_pdf_text(input_path), False

    return ocr_pdf_pages(input_path, dpi=dpi), True


def run_pipeline(
    input_path: str,
    output_path: str | None = None,
    force_ocr: bool = False,
    dpi: int = 300,
) -> PipelineResult:
    """Run the full extraction pipeline and write an Excel workbook.

    Args:
        input_path: Path to a PDF or image (jpg/png) file.
        output_path: Where to write the .xlsx workbook. Defaults to
            ``outputs/<input filename stem>_extracted.xlsx``.
        force_ocr: Skip the text-layer check and OCR every page (use this
            for a PDF that has a text layer but garbled/unusable text, e.g.
            a badly-encoded scan-with-invisible-text PDF).
        dpi: Rasterization DPI used for OCR. Higher is more accurate but
            slower; 300 is a reasonable default, 400+ helps with small
            print / dense tables.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(input_path)

    if output_path is None:
        stem = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join("outputs", f"{stem}_extracted.xlsx")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    pages, used_ocr = _load_pages(input_path, force_ocr, dpi)
    statement_pages = find_statement_pages(pages)

    results: Dict[str, Dict[str, pd.DataFrame]] = {}
    summaries: Dict[str, StatementSummary] = {}

    for statement_key, page_numbers in statement_pages.items():
        raw_df = build_statement_dataframe(pages, page_numbers)
        mapping = standardize(raw_df, statement_key)
        results[statement_key] = {
            "raw": raw_df,
            "standardized": mapping.standardized,
            "unmapped": mapping.unmapped,
        }
        summaries[statement_key] = StatementSummary(
            pages_found=page_numbers,
            rows_extracted=len(raw_df),
            rows_standardized=len(mapping.standardized),
            rows_unmapped=len(mapping.unmapped),
        )

    write_workbook(output_path, results)

    return PipelineResult(
        output_path=output_path,
        used_ocr=used_ocr,
        page_count=len(pages),
        statement_summaries=summaries,
        tables=results,
    )
