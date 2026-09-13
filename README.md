# Annual Report Extractor

A small Python toolkit that pulls structured financial statements out of
company annual reports — PDF or scanned/photographed pages — and organizes
them into a clean Excel workbook for equity research and valuation work.

No local setup? Push this repo to GitHub, then open
`notebooks/colab_demo.ipynb` on GitHub and click "Open in Colab" (or go to
[colab.research.google.com](https://colab.research.google.com), File → Open
notebook → GitHub, and paste your repo URL) to run the whole pipeline in the
browser.

Point it at an annual report PDF and it will:

1. Detect whether the PDF has a real text layer or needs OCR (scanned reports, photographed pages)
2. Score every page for Balance Sheet / Statement of Profit & Loss / Cash Flow Statement content, and locate the right pages automatically
3. Parse those pages' tables into `(line item, value_1, value_2, ...)` rows — using ruled-table detection where available, and a whitespace-alignment fallback otherwise (most Indian annual reports don't draw grid lines around their financial statements)
4. Standardize the messy real-world labels ("Revenue from operations", "Net Sales", "Total Income") onto a canonical Schedule III / Ind AS-style schema, so statements from different companies come out in a comparable shape
5. Export everything — standardized, raw, and unmapped — to a formatted Excel workbook, plus a Summary sheet with a few headline ratios

Nothing is ever silently dropped: any row that doesn't match the schema
lands in a `(unmapped)` sheet instead of disappearing, so you can see
exactly what the tool missed.

## Why this exists

Manually re-typing Balance Sheet / P&L / Cash Flow line items out of a
150-page annual report PDF into a model is slow and error-prone. This tool
automates the first pass — get the numbers into a workbook fast, in a
structure a DCF or ratio-analysis model can consume directly — while being
transparent about what it's unsure of, so you can trust it enough to use
for real research instead of a black box.

## Quick start

```bash
pip install -e .
arx path/to/annual_report.pdf
```

This writes `outputs/annual_report_extracted.xlsx`.

Options:

```bash
arx report.pdf -o my_output.xlsx     # custom output path
arx report.pdf --ocr                 # force OCR even if a text layer exists
arx report.pdf --ocr --dpi 400       # higher-DPI OCR for dense/small print
arx report.pdf -v                    # print a per-statement extraction summary
```

For a scanned report or a photographed page, just point it at the file —
image inputs (`.jpg`, `.jpeg`, `.png`) and non-text-layer PDFs are OCR'd
automatically.

## Multi-year historical extraction (batch mode)

Point it at a folder of per-statement, per-year files and get one workbook
with a historical block per statement — line items down the side, fiscal
years across the top:

```bash
arx-batch path/to/statements/ -o outputs/historical.xlsx
arx-batch path/to/statements/ --basis standalone     # default is consolidated
```

```
                                       FY2022-23  FY2023-24  FY2024-25
Revenue from Operations                  14100.0    16200.0    18500.0
Other Income                               240.0      280.0      320.0
Total Income                             14340.0    16480.0    18820.0
...
```

Three things make this trustworthy rather than merely convenient:

- **Columns are identified, not assumed.** A SEBI quarterly-results filing
  shows ten numeric columns (three quarters and two full years, standalone
  then consolidated). The header rows are parsed to work out which is
  which, so the annual consolidated column goes into your historicals and a
  quarter figure never does. If the header can't be read confidently, the
  file is reported rather than merged.
- **Every statement is footed automatically.** Revenue + Other Income =
  Total Income; Assets = Equity + Liabilities; CFO + CFI + CFF = net
  movement in cash. OCR digit errors produce plausible-looking numbers that
  no amount of proofreading catches, but they break these identities. Any
  break is reported in a `Checks` sheet with the size of the discrepancy.
- **Overlapping years are cross-checked.** Each file also carries a
  prior-year column, so a 2024-25 file and a 2023-24 file both report
  FY2023-24. Where two files disagree on the same figure, both values are
  reported in a `Conflicts` sheet instead of one silently winning. (This
  also means N years of files usually yields N+1 years of history.)

Rows whose column position is uncertain — typically because OCR dropped a
column — are excluded from the historical block and listed under `Needs
Review`, rather than being placed under a year they might not belong to.

## Web demo

```bash
pip install -e ".[demo]"
streamlit run app.py
```

Upload a PDF or image, preview the extracted tables by statement (with raw
and unmapped rows in expandable sections), and download the workbook.

## How it's built

```
src/arx/
  extraction/
    pdf_reader.py    # pdfplumber text-layer + ruled-table extraction
    ocr.py           # pytesseract + pdf2image OCR fallback
    models.py        # PageContent data model shared across the pipeline
  locate/
    statement_finder.py  # scores pages by title/line-item keyword density
  parse/
    numbers.py       # Indian-number-format-aware numeric parsing
    rows.py          # splits a row of cells into (label, [values])
    table_parser.py  # assembles a statement's pages into one DataFrame
  standardize/
    schema.py        # canonical Schedule III-style line-item definitions
    mapper.py         # regex-based label -> canonical schema mapping
  export/
    excel_writer.py  # formatted multi-sheet .xlsx output
  pipeline.py        # orchestrates the above end to end
cli.py / app.py       # command-line and Streamlit entry points
tests/                 # unit tests + a synthetic end-to-end fixture generator
```

### Notable design decisions (useful to know, and to talk about)

- **Statement location is a scoring problem, not a keyword search.** A
  Directors' Report or MD&A section mentions "profit" and "assets"
  constantly; the locator scores pages on both title phrases *and*
  line-item density (how many well-known Schedule III line items appear),
  so it doesn't latch onto prose.
- **Whitespace alignment, not ruling lines, is the common case.** Most
  Indian annual reports lay out financial statement tables using aligned
  whitespace rather than visible grid lines, so `pdfplumber`'s ruled-table
  detection often finds nothing. The fallback parser scans each line for
  trailing number-shaped substrings and peels them off one at a time —
  robust even when column gaps collapse to a single space (which happens
  with `pdfplumber`'s layout-preserving text mode on some PDFs).
- **First-match-wins, duplicates are flagged, nothing is dropped.**
  Standardization keeps the first row that matches a canonical line item
  and routes any later duplicate match to the unmapped sheet with a reason
  — silently overwriting or summing would be worse than surfacing the
  ambiguity for a valuation tool.
- **Numeric parsing matches how Indian statements actually print numbers**:
  comma grouping (including the Indian `12,34,567` style), parenthesized
  negatives, en/em-dash "nil" markers, and `₹`/`Rs.` prefixes.

### Known limitations

- **OCR is meaningfully less reliable than text-layer extraction**,
  especially for dense multi-column tables — digit confusion and column
  misalignment are common. Treat OCR output as a fast first pass to
  spot-check against the source page, not a final number.
- **The canonical schema covers standard Ind AS / Schedule III line items.**
  A company with materially different statement structure (banks, NBFCs,
  insurers) will have more rows land in the unmapped sheet — extend
  `standardize/schema.py` with additional patterns as you hit them.
- Multi-year columns are captured positionally (`value_1`, `value_2`, ...)
  in the order they appear on the page; the tool doesn't currently parse
  column headers into explicit fiscal-year labels.

## Running the tests

```bash
pip install -e . pytest
pytest tests/ -v
```

`tests/make_synthetic_report.py` generates a synthetic Schedule III-style
annual report PDF (prose pages + whitespace-aligned statements) used as an
end-to-end fixture, so the full pipeline can be exercised without needing a
real company's report in the repo.

## License

MIT — see `LICENSE`.
