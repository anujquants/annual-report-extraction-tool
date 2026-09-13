"""
arx - Annual Report eXtractor
==============================

A small toolkit for pulling structured financial statements (Balance Sheet,
Statement of Profit & Loss, Cash Flow Statement) out of company annual
report PDFs (and scanned PDFs / images via OCR), and organizing them into
a clean Excel workbook for equity research and valuation work.

Pipeline:
    load (text or OCR) -> locate statement pages -> parse tables into
    (label, values) rows -> standardize labels to a canonical schema
    -> export to Excel
"""

__version__ = "0.1.0"
