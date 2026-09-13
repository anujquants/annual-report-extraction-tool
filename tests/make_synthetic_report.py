"""Generate a synthetic 'annual report' PDF for end-to-end pipeline testing.

Mimics the shape of a real Indian Schedule III annual report: prose pages
that mention financial terms in passing (to test the locator doesn't get
fooled), followed by whitespace-aligned (no ruling lines) Balance Sheet,
P&L, and Cash Flow pages -- since that's the most common real-world layout
and the harder case for table extraction.
"""

import sys

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT_PATH = sys.argv[1] if len(sys.argv) > 1 else "/tmp/synthetic_annual_report.pdf"


def draw_line(c, y, text, font="Courier", size=9):
    c.setFont(font, size)
    c.drawString(50, y, text)
    return y - 14


def prose_page(c, title, paragraphs):
    y = 780
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, title)
    y -= 30
    c.setFont("Helvetica", 10)
    for para in paragraphs:
        for line in para:
            c.drawString(50, y, line)
            y -= 14
        y -= 10
    c.showPage()


def main():
    c = canvas.Canvas(OUT_PATH, pagesize=A4)

    prose_page(
        c,
        "Directors' Report",
        [
            [
                "The Company delivered a strong performance during the year, with profit",
                "growing steadily. The Board is pleased to report improved margins and a",
                "healthy balance sheet position across all key metrics.",
            ],
            [
                "Total income for the year reflects continued momentum in our core segments,",
                "and the management remains confident about future profit growth.",
            ],
        ],
    )

    prose_page(
        c,
        "Management Discussion and Analysis",
        [
            [
                "Our cash flow generation remained robust, supporting continued investment",
                "in capacity expansion. Profitability metrics improved year on year.",
            ],
        ],
    )

    # ---- Balance Sheet (whitespace-aligned, no ruling lines) ----
    y = 780
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Balance Sheet as at 31 March 2025")
    y -= 30
    bs_lines = [
        "                                              As at 31-Mar-2025    As at 31-Mar-2024",
        "ASSETS",
        "Non-current assets",
        "Property, Plant and Equipment                     12,500.00           11,200.00",
        "Capital work-in-progress                              300.00              450.00",
        "Other Intangible Assets                               150.00              120.00",
        "Non-current investments                             1,000.00              900.00",
        "Total Non-current assets                           13,950.00           12,670.00",
        "Current assets",
        "Inventories                                         2,300.00            2,100.00",
        "Trade receivables                                   3,400.00            3,050.00",
        "Cash and cash equivalents                             850.00              620.00",
        "Other current assets                                  400.00              380.00",
        "Total current assets                                6,950.00            6,150.00",
        "Total Assets                                       20,900.00           18,820.00",
        "EQUITY AND LIABILITIES",
        "Equity Share Capital                                1,200.00            1,200.00",
        "Other Equity                                       12,300.00           10,800.00",
        "Total Equity                                       13,500.00           12,000.00",
        "Non-current liabilities",
        "Borrowings                                          4,000.00            3,800.00",
        "Total Non-current liabilities                       4,000.00            3,800.00",
        "Current liabilities",
        "Current borrowings                                    900.00              950.00",
        "Trade payables                                      1,800.00            1,650.00",
        "Other current liabilities                             700.00              420.00",
        "Total current liabilities                           3,400.00            3,020.00",
        "Total Equity and Liabilities                       20,900.00           18,820.00",
    ]
    for line in bs_lines:
        y = draw_line(c, y, line)
    c.showPage()

    # ---- Statement of Profit and Loss ----
    y = 780
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Statement of Profit and Loss for the year ended 31 March 2025")
    y -= 30
    pl_lines = [
        "                                              FY 2024-25          FY 2023-24",
        "Revenue from operations                            18,500.00           16,200.00",
        "Other Income                                          320.00              280.00",
        "Total Income                                       18,820.00           16,480.00",
        "Expenses",
        "Cost of materials consumed                          9,200.00            8,100.00",
        "Employee benefits expense                           2,800.00            2,500.00",
        "Finance costs                                         (450.00)            (410.00)",
        "Depreciation and amortisation expense               1,100.00              980.00",
        "Other expenses                                      1,900.00            1,750.00",
        "Total Expenses                                     15,450.00           13,740.00",
        "Profit before tax                                   3,370.00            2,740.00",
        "Current Tax                                           850.00              690.00",
        "Deferred Tax                                           40.00               30.00",
        "Profit for the year                                 2,480.00            2,020.00",
        "Basic (in Rs.)                                         20.67               16.83",
        "Diluted (in Rs.)                                       20.55               16.70",
    ]
    for line in pl_lines:
        y = draw_line(c, y, line)
    c.showPage()

    # ---- Cash Flow Statement ----
    y = 780
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Cash Flow Statement for the year ended 31 March 2025")
    y -= 30
    cf_lines = [
        "                                              FY 2024-25          FY 2023-24",
        "Net cash generated from operating activities        3,100.00            2,600.00",
        "Net cash used in investing activities              (1,650.00)          (1,400.00)",
        "Net cash used in financing activities                (900.00)            (750.00)",
        "Net increase in cash and cash equivalents             550.00              450.00",
        "Cash and cash equivalents at the beginning of the year 300.00              170.00",
        "Cash and cash equivalents at the end of the year      850.00              620.00",
    ]
    for line in cf_lines:
        y = draw_line(c, y, line)
    c.showPage()

    c.save()
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
