"""Command-line interface: ``arx report.pdf`` -> ``outputs/report_extracted.xlsx``."""

from __future__ import annotations

import argparse
import sys

from arx.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arx",
        description="Extract standardized financial statements (Balance Sheet, P&L, "
        "Cash Flow) from an annual report PDF or image into an Excel workbook.",
    )
    parser.add_argument("input", help="Path to the annual report PDF, or a JPG/PNG page image.")
    parser.add_argument(
        "-o", "--output", default=None,
        help="Output .xlsx path (default: outputs/<input filename>_extracted.xlsx)",
    )
    parser.add_argument(
        "--ocr", action="store_true",
        help="Force OCR even if the PDF appears to have a text layer.",
    )
    parser.add_argument(
        "--dpi", type=int, default=300,
        help="Rasterization DPI for OCR (default: 300; try 400+ for dense/small print).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print a per-statement summary (pages found, rows extracted/mapped/unmapped).",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = run_pipeline(args.input, output_path=args.output, force_ocr=args.ocr, dpi=args.dpi)
    except FileNotFoundError:
        print(f"error: file not found: {args.input}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"Processed {result.page_count} page(s){' via OCR' if result.used_ocr else ''}.")
    for key, summary in result.statement_summaries.items():
        if not summary.pages_found:
            print(f"  {key}: not found")
            continue
        print(
            f"  {key}: pages {summary.pages_found} -> "
            f"{summary.rows_extracted} rows extracted, "
            f"{summary.rows_standardized} standardized, "
            f"{summary.rows_unmapped} unmapped"
        )
    print(f"Workbook written to: {result.output_path}")

    if args.verbose:
        print("\nTip: check the '(unmapped)' sheets for line items the schema didn't recognize.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
