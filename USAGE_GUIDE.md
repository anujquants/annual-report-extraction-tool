# Step-by-Step: Setting Up and Running the Annual Report Extractor

This walks through everything from a fresh machine to a filled-in Excel
workbook from a real annual report PDF.

## 1. Prerequisites

You need three things installed on your machine:

| Tool | Why | Check if installed |
|---|---|---|
| Python 3.9+ | Runs the tool | `python3 --version` |
| pip | Installs Python packages | `pip --version` |
| Tesseract OCR | Only needed for scanned PDFs / photos | `tesseract --version` |

**Installing Tesseract** (skip this if you'll only ever use text-based PDFs,
i.e. reports downloaded from a company's investor relations page or BSE/NSE
— those almost always have a text layer):

- macOS: `brew install tesseract`
- Ubuntu/Debian: `sudo apt install tesseract-ocr`
- Windows: install from https://github.com/UB-Mannheim/tesseract/wiki, then
  make sure `tesseract.exe` is on your PATH

## 2. Get the code onto your machine

If you downloaded the zip I sent: unzip it anywhere, e.g.:

```bash
unzip annual-report-extractor.zip
cd annual-report-extractor
```

If you've already pushed it to GitHub:

```bash
git clone https://github.com/<your-username>/annual-report-extractor.git
cd annual-report-extractor
```

## 3. Install it

From inside the `annual-report-extractor` folder:

```bash
pip install -e .
```

This installs the Python dependencies (pdfplumber, PyMuPDF, pandas,
openpyxl, etc.) and registers the `arx` command on your machine. Confirm it
worked:

```bash
arx --help
```

## 4. Get an annual report PDF

Download one from a company's investor relations page, or from
[BSE](https://www.bseindia.com) / [NSE](https://www.nseindia.com) /
[screener.in](https://www.screener.in) (search the company → Annual Reports).
Save it somewhere you can find it, e.g. `~/Downloads/company_ar_2025.pdf`.

## 5. Run the extractor

```bash
arx ~/Downloads/company_ar_2025.pdf -v
```

The `-v` flag prints a summary as it runs, e.g.:

```
Processed 180 page(s).
  balance_sheet: pages [92] -> 24 rows extracted, 21 standardized, 3 unmapped
  profit_and_loss: pages [94] -> 17 rows extracted, 16 standardized, 1 unmapped
  cash_flow: pages [96] -> 8 rows extracted, 6 standardized, 2 unmapped
Workbook written to: outputs/company_ar_2025_extracted.xlsx
```

That tells you which pages it found for each statement, and how many line
items it successfully mapped vs. couldn't place.

## 6. Open the workbook

Open `outputs/company_ar_2025_extracted.xlsx`. It has:

- **Summary** — a handful of headline figures and ratios (revenue, net
  profit, total assets, ROE/ROA approximations) pulled together across
  statements, if enough data was found
- **Balance Sheet** / **P&L** / **Cash Flow** — the standardized line
  items, in standard order, ready to plug into a model
- **... (raw)** — everything extracted from that statement's pages before
  any mapping, in case you want to sanity-check the source numbers
- **... (unmapped)** — rows the tool found but couldn't confidently match
  to a standard line item (see step 8)

`value_1` is generally the most recent year shown on the page, `value_2` the
prior year, and so on — check against the raw sheet's `page` column if
you want to confirm against the source PDF.

## 7. Try the visual demo (optional, good for interviews)

```bash
pip install -e ".[demo]"
streamlit run app.py
```

This opens a browser tab where you upload a PDF and see everything —
standardized tables, raw rows, unmapped rows — live, with a download button
for the workbook. Much better than a terminal for walking someone through
what the tool does.

## 8. If something looks off

**A statement wasn't found at all (0 rows / "not found")**
The page-locator didn't find a page that looked enough like that statement.
Open the source PDF, find the actual page number, and check whether it's a
non-standard title (e.g. "Balance Sheet of the Standalone Financial
Statements" vs. a consolidated one on a different page — the tool currently
picks whichever scores highest, which is usually the first one it hits).

**Lots of rows in the "unmapped" sheet**
This is expected for companies whose statement structure differs from
standard manufacturing/Ind AS Schedule III presentation — banks, NBFCs, and
insurers in particular use different line items ("Interest earned" instead
of "Revenue from operations", etc.). Open `src/arx/standardize/schema.py`
and add a pattern for the missing line item, e.g.:

```python
SchemaItem("interest_earned", "Interest Earned", [r"interest\s+earned"]),
```

Re-run `arx` and it'll pick it up.

**Numbers look shifted between value_1/value_2**
This usually means a value column was nil ("-") and got treated as missing
rather than a placeholder — check the raw sheet's row against the source
page to confirm alignment.

**OCR output is messy**
Expected — OCR is meaningfully less accurate than text-layer extraction,
especially for dense tables. Try a higher `--dpi` (e.g. 400), and treat the
output as a first draft to spot-check against the source page rather than a
final number.

## 9. Push it to GitHub

The project is already a git repo with an initial commit. From inside the
folder:

```bash
git remote add origin https://github.com/<your-username>/annual-report-extractor.git
git branch -M main
git push -u origin main
```

(Create the empty repo on GitHub first via "New repository" — don't
initialize it with a README there, since you already have one.)

## 10. Using it for real valuation work

A practical loop once it's set up:

1. Pull the annual report PDF for the company you're modeling
2. `arx company.pdf -v`
3. Open the workbook, copy the **standardized** columns into your DCF/ratio
   model (they're already ordered and labeled)
4. Check the **unmapped** sheet for anything your model needs that didn't
   map — usually a handful of line items, faster to grab manually than to
   extend the schema for a one-off
5. Repeat for the prior 2-3 years of reports if you want a longer time
   series than the two years a single annual report usually shows
