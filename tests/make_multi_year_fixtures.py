"""Generate a folder of per-year, per-statement PDFs for testing batch mode.

Mimics the way an analyst's folder actually looks -- separate files per
statement per year, named like "2024-25 Balance Sheet.pdf" -- and uses
overlapping prior-year columns so the cross-file agreement check has
something to verify.
"""

import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/multi_year"

# Figures are internally consistent so the footing checks should all pass.
# FY2023-24 appears as the current year of one file and the prior year of
# the next, which is exactly the overlap the conflict checker looks at.
YEARS = {
    "2023-24": {
        "dates": ("31-Mar-2024", "31-Mar-2023"),
        "pl": [
            ("Revenue from operations", 16200.00, 14100.00),
            ("Other Income", 280.00, 240.00),
            ("Total Income", 16480.00, 14340.00),
            ("Cost of materials consumed", 8100.00, 7200.00),
            ("Employee benefits expense", 2500.00, 2250.00),
            ("Finance costs", 410.00, 380.00),
            ("Depreciation and amortisation expense", 980.00, 900.00),
            ("Other expenses", 1750.00, 1600.00),
            ("Total Expenses", 13740.00, 12330.00),
            ("Profit before tax", 2740.00, 2010.00),
            ("Current Tax", 690.00, 510.00),
            ("Deferred Tax", 30.00, 25.00),
            ("Profit for the year", 2020.00, 1475.00),
        ],
        "bs": [
            ("Property, Plant and Equipment", 11200.00, 10500.00),
            ("Total Non-current assets", 12670.00, 11900.00),
            ("Inventories", 2100.00, 1950.00),
            ("Trade receivables", 3050.00, 2800.00),
            ("Cash and cash equivalents", 620.00, 540.00),
            ("Other current assets", 380.00, 360.00),
            ("Total current assets", 6150.00, 5650.00),
            ("Total Assets", 18820.00, 17550.00),
            ("Equity Share Capital", 1200.00, 1200.00),
            ("Other Equity", 10800.00, 9400.00),
            ("Total Equity", 12000.00, 10600.00),
            ("Total Non-current liabilities", 3800.00, 3900.00),
            ("Total current liabilities", 3020.00, 3050.00),
            ("Total Equity and Liabilities", 18820.00, 17550.00),
        ],
        "cf": [
            ("Net cash generated from operating activities", 2600.00, 2200.00),
            ("Net cash used in investing activities", -1400.00, -1250.00),
            ("Net cash used in financing activities", -750.00, -700.00),
            ("Net increase in cash and cash equivalents", 450.00, 250.00),
            ("Cash and cash equivalents at the beginning of the year", 170.00, -80.00),
            ("Cash and cash equivalents at the end of the year", 620.00, 170.00),
        ],
    },
    "2024-25": {
        "dates": ("31-Mar-2025", "31-Mar-2024"),
        "pl": [
            ("Revenue from operations", 18500.00, 16200.00),
            ("Other Income", 320.00, 280.00),
            ("Total Income", 18820.00, 16480.00),
            ("Cost of materials consumed", 9200.00, 8100.00),
            ("Employee benefits expense", 2800.00, 2500.00),
            ("Finance costs", 450.00, 410.00),
            ("Depreciation and amortisation expense", 1100.00, 980.00),
            ("Other expenses", 1900.00, 1750.00),
            ("Total Expenses", 15450.00, 13740.00),
            ("Profit before tax", 3370.00, 2740.00),
            ("Current Tax", 850.00, 690.00),
            ("Deferred Tax", 40.00, 30.00),
            ("Profit for the year", 2480.00, 2020.00),
        ],
        "bs": [
            ("Property, Plant and Equipment", 12500.00, 11200.00),
            ("Total Non-current assets", 13950.00, 12670.00),
            ("Inventories", 2300.00, 2100.00),
            ("Trade receivables", 3400.00, 3050.00),
            ("Cash and cash equivalents", 850.00, 620.00),
            ("Other current assets", 400.00, 380.00),
            ("Total current assets", 6950.00, 6150.00),
            ("Total Assets", 20900.00, 18820.00),
            ("Equity Share Capital", 1200.00, 1200.00),
            ("Other Equity", 12300.00, 10800.00),
            ("Total Equity", 13500.00, 12000.00),
            ("Total Non-current liabilities", 4000.00, 3800.00),
            ("Total current liabilities", 3400.00, 3020.00),
            ("Total Equity and Liabilities", 20900.00, 18820.00),
        ],
        "cf": [
            ("Net cash generated from operating activities", 3100.00, 2600.00),
            ("Net cash used in investing activities", -1650.00, -1400.00),
            ("Net cash used in financing activities", -900.00, -750.00),
            ("Net increase in cash and cash equivalents", 550.00, 450.00),
            ("Cash and cash equivalents at the beginning of the year", 300.00, 170.00),
            ("Cash and cash equivalents at the end of the year", 850.00, 620.00),
        ],
    },
}

TITLES = {
    "bs": "Balance Sheet as at {d0}",
    "pl": "Statement of Profit and Loss for the year ended {d0}",
    "cf": "Cash Flow Statement for the year ended {d0}",
}
FILENAMES = {
    "bs": "{fy} Balance Sheet.pdf",
    "pl": "{fy} Income Statement.pdf",
    "cf": "{fy} Cash Flow.pdf",
}


def fmt(value):
    text = f"{abs(value):,.2f}"
    return f"({text})" if value < 0 else text


def write_statement(path, title, dates, rows):
    c = canvas.Canvas(path, pagesize=A4)
    y = 780
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y, title)
    y -= 28
    c.setFont("Courier", 9)
    c.drawString(50, y, f"{'Particulars':<44}{'As at ' + dates[0]:>18}{'As at ' + dates[1]:>18}")
    y -= 18
    for label, current, prior in rows:
        c.drawString(50, y, f"{label:<44}{fmt(current):>18}{fmt(prior):>18}")
        y -= 14
    c.showPage()
    c.save()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for fy, data in YEARS.items():
        for kind in ("bs", "pl", "cf"):
            path = os.path.join(OUT_DIR, FILENAMES[kind].format(fy=fy))
            write_statement(path, TITLES[kind].format(d0=data["dates"][0]),
                            data["dates"], data[kind])
            print("wrote", path)


if __name__ == "__main__":
    main()
