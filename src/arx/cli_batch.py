"""``arx-batch``: turn a folder of statement PDFs into one historical workbook."""

from __future__ import annotations

import argparse
import glob
import os
import sys
from typing import List

from arx.batch import build_historical, process_file
from arx.export.excel_writer import write_historical_workbook
from arx.validate import run_checks, summarize


def _expand_inputs(inputs: List[str]) -> List[str]:
    paths: List[str] = []
    for item in inputs:
        if os.path.isdir(item):
            for ext in ("*.pdf", "*.PDF", "*.jpg", "*.jpeg", "*.png"):
                paths.extend(sorted(glob.glob(os.path.join(item, ext))))
        elif any(ch in item for ch in "*?["):
            paths.extend(sorted(glob.glob(item)))
        else:
            paths.append(item)
    seen = set()
    unique = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arx-batch",
        description="Extract several annual/quarterly statement PDFs at once and "
                    "consolidate them into a multi-year historical Excel workbook.",
    )
    parser.add_argument("inputs", nargs="+",
                        help="PDF/image files, a glob, or a folder containing them.")
    parser.add_argument("-o", "--output", default="outputs/historical.xlsx",
                        help="Output .xlsx path (default: outputs/historical.xlsx)")
    parser.add_argument("--basis", choices=["consolidated", "standalone"], default="consolidated",
                        help="Which reporting basis to prefer when a filing shows both "
                             "(default: consolidated, the usual choice for valuation).")
    parser.add_argument("--ocr", action="store_true",
                        help="Force OCR even if a PDF appears to have a text layer.")
    parser.add_argument("--dpi", type=int, default=300,
                        help="Rasterization DPI for OCR (default: 300).")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    paths = _expand_inputs(args.inputs)
    if not paths:
        print("error: no input files matched", file=sys.stderr)
        return 1

    all_results = []
    for path in paths:
        print(f"Reading {os.path.basename(path)} ...", flush=True)
        try:
            results = process_file(path, force_ocr=args.ocr, dpi=args.dpi)
        except Exception as exc:  # keep going; one bad file shouldn't sink the run
            print(f"  ! failed: {exc}", file=sys.stderr)
            continue
        if not results:
            print("  ! no statements found in this file")
            continue
        for r in results:
            print(f"  {r.statement}: {len(r.standardized)} line items, "
                  f"{len(r.layout.columns)} columns "
                  f"({'dated' if r.layout.confident else 'undated'})")
        all_results.extend(results)

    if not all_results:
        print("error: nothing could be extracted from the given files", file=sys.stderr)
        return 1

    historical = build_historical(all_results, basis_preference=args.basis)
    checks = run_checks(historical.tables)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    write_historical_workbook(args.output, historical, checks)

    print()
    for statement, table in historical.tables.items():
        print(f"{statement}: {len(table)} line items x {len(table.columns)} years "
              f"({', '.join(table.columns)})")
    print(f"Consistency checks: {summarize(checks)}")
    if not historical.conflicts.empty:
        print(f"Cross-file disagreements: {len(historical.conflicts)} (see 'Conflicts' sheet)")
    if not historical.needs_review.empty:
        print(f"Rows needing review: {len(historical.needs_review)} (see 'Needs Review' sheet)")
    print(f"Workbook written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
