"""Canonical line-item schemas for the three core financial statements,
modelled on Indian Schedule III / Ind AS presentation (the format used by
listed Indian companies) since that's the most common source format for
this tool.

Each canonical item is defined by:
    key: stable machine-friendly identifier
    label: human-readable display name used in the output workbook
    patterns: regex patterns checked against the *normalized* raw label
        (lowercased, punctuation stripped, extra whitespace collapsed).
        Checked in the order given across the whole schema for a
        statement -- put more specific / "total" patterns before generic
        component patterns so e.g. "Total current assets" doesn't get
        swallowed by a generic "assets" pattern.

This is intentionally scoped to the line items that appear in the vast
majority of Indian company financial statements. Company-specific extra
line items (e.g. a bank's "Interest earned" instead of "Revenue from
operations") won't match and will show up in the "Unmapped" sheet instead
of being silently dropped -- extend the patterns below as you encounter
more formats.
"""

from __future__ import annotations

from typing import List, NamedTuple, Optional


class SchemaItem(NamedTuple):
    key: str
    label: str
    patterns: List[str]
    # Plain-language form of this line item, used only as a fuzzy-matching
    # fallback when OCR has damaged a label badly enough that no regex
    # matches ("Protit/(Loss) before tax", "Deterred Tax"). Defaults to the
    # lowercased display label.
    fuzzy_key: Optional[str] = None

    @property
    def match_key(self) -> str:
        return self.fuzzy_key or self.label.lower()


BALANCE_SHEET_SCHEMA: List[SchemaItem] = [
    # --- totals first (order matters: most specific phrase first) ---
    SchemaItem("total_equity_and_liabilities", "Total Equity and Liabilities",
               [r"total\s+equity\s+and\s+liabilit"]),
    SchemaItem("total_assets", "Total Assets", [r"^total\s+assets$"]),
    SchemaItem("total_current_assets", "Total Current Assets", [r"total\s+current\s+assets"]),
    SchemaItem("total_noncurrent_assets", "Total Non-Current Assets",
               [r"total\s+non.?current\s+assets"]),
    SchemaItem("total_current_liabilities", "Total Current Liabilities",
               [r"total\s+current\s+liabilit"]),
    SchemaItem("total_noncurrent_liabilities", "Total Non-Current Liabilities",
               [r"total\s+non.?current\s+liabilit"]),
    SchemaItem("total_equity", "Total Equity", [r"^total\s+equity$"]),
    # --- equity ---
    SchemaItem("equity_share_capital", "Equity Share Capital", [r"equity\s+share\s+capital"]),
    SchemaItem("other_equity", "Other Equity", [r"^other\s+equity$", r"reserves\s+and\s+surplus"]),
    # --- non-current liabilities ---
    SchemaItem("borrowings_noncurrent", "Borrowings (Non-Current)",
               [r"^(non.?current\s+)?borrowings$", r"long.?term\s+borrowings"]),
    SchemaItem("provisions_noncurrent", "Provisions (Non-Current)", [r"^provisions$"]),
    SchemaItem("deferred_tax_liabilities", "Deferred Tax Liabilities (Net)",
               [r"deferred\s+tax\s+liabilit"]),
    # --- current liabilities ---
    SchemaItem("borrowings_current", "Borrowings (Current)", [r"current\s+borrowings",
                                                               r"short.?term\s+borrowings"]),
    SchemaItem("trade_payables", "Trade Payables", [r"trade\s+payabl"]),
    SchemaItem("other_current_liabilities", "Other Current Liabilities",
               [r"other\s+current\s+liabilit"]),
    # --- non-current assets ---
    SchemaItem("ppe", "Property, Plant and Equipment", [r"property,?\s+plant\s+and\s+equipment"]),
    SchemaItem("cwip", "Capital Work-in-Progress", [r"capital\s+work.?in.?progress"]),
    SchemaItem("goodwill", "Goodwill", [r"^goodwill$"]),
    SchemaItem("intangible_assets", "Other Intangible Assets", [r"intangible\s+assets"]),
    SchemaItem("investments_noncurrent", "Investments (Non-Current)",
               [r"non.?current\s+investments", r"^investments$"]),
    SchemaItem("other_noncurrent_assets", "Other Non-Current Assets",
               [r"other\s+non.?current\s+assets"]),
    # --- current assets ---
    SchemaItem("inventories", "Inventories", [r"inventor"]),
    SchemaItem("trade_receivables", "Trade Receivables", [r"trade\s+receivabl"]),
    SchemaItem("cash_and_equivalents", "Cash and Cash Equivalents",
               [r"cash\s+and\s+cash\s+equivalent"]),
    SchemaItem("bank_balances_other", "Bank Balances (Other than Cash Equivalents)",
               [r"bank\s+balances?\s+other"]),
    SchemaItem("other_current_assets", "Other Current Assets", [r"other\s+current\s+assets"]),
]

PROFIT_AND_LOSS_SCHEMA: List[SchemaItem] = [
    SchemaItem("total_income", "Total Income", [r"^total\s+income$"]),
    SchemaItem("total_expenses", "Total Expenses", [r"^total\s+expenses$"]),
    SchemaItem("revenue", "Revenue from Operations", [r"revenue\s+from\s+operations"]),
    SchemaItem("other_income", "Other Income", [r"^other\s+income$"]),
    SchemaItem("cost_of_materials", "Cost of Materials Consumed",
               [r"cost\s+of\s+materials?\s+consumed"]),
    SchemaItem("purchases_stock_in_trade", "Purchases of Stock-in-Trade",
               [r"purchases?\s+of\s+stock.?in.?trade", r"purchase\s+of\s+traded\s+goods"]),
    SchemaItem("changes_in_inventories", "Changes in Inventories",
               [r"changes?\s+in\s+inventor"]),
    SchemaItem("employee_expenses", "Employee Benefits Expense",
               [r"employee\s+benefit"]),
    SchemaItem("finance_costs", "Finance Costs", [r"finance\s+costs?"]),
    SchemaItem("depreciation_amortisation", "Depreciation and Amortisation Expense",
               [r"depreciation\s+and\s+amortisation"]),
    SchemaItem("other_expenses", "Other Expenses", [r"^other\s+expenses$"]),
    SchemaItem("profit_before_exceptional_items", "Profit Before Exceptional Items and Tax",
               [r"profit(?:\s*/\s*\(?loss\)?)?\s+before\s+exceptional"]),
    SchemaItem("exceptional_items", "Exceptional Items", [r"^exceptional\s+items?$"]),
    SchemaItem("profit_before_tax", "Profit Before Tax",
               [r"profit(?:\s*/\s*\(?loss\)?)?\s+before\s+tax"]),
    SchemaItem("current_tax", "Current Tax", [r"^current\s+tax$"]),
    SchemaItem("deferred_tax", "Deferred Tax", [r"^deferred\s+tax(\s+charge)?$"]),
    SchemaItem("tax_earlier_years", "Tax for Earlier Years", [r"tax\s+for\s+earlier\s+years?"]),
    SchemaItem("tax_expense", "Total Tax Expense", [r"^tax\s+expense$"]),
    SchemaItem("net_profit", "Profit for the Year",
               [r"profit(?:\s*/\s*\(?loss\)?)?\s+after\s+tax\s+for\s+the\s+(?:year|period)",
                r"profit(?:\s*/\s*\(?loss\)?)?\s+for\s+the\s+(?:year|period)"],
               fuzzy_key="profit after tax for the period"),
    SchemaItem("total_comprehensive_income", "Total Comprehensive Income for the Period",
               [r"total\s+comprehensive\s+income"]),
    SchemaItem("eps_basic", "Basic EPS", [r"basic\s*\(?in\s*rs", r"^basic$"]),
    SchemaItem("eps_diluted", "Diluted EPS", [r"diluted\s*\(?in\s*rs", r"^diluted$"]),
]

CASH_FLOW_SCHEMA: List[SchemaItem] = [
    SchemaItem("cash_from_operations", "Net Cash from Operating Activities",
               [r"net\s+cash\s+(generated\s+from|from|used\s+in)\s+operating"]),
    SchemaItem("cash_from_investing", "Net Cash from Investing Activities",
               [r"net\s+cash\s+(generated\s+from|from|used\s+in)\s+investing"]),
    SchemaItem("cash_from_financing", "Net Cash from Financing Activities",
               [r"net\s+cash\s+(generated\s+from|from|used\s+in)\s+financing"]),
    SchemaItem("net_change_in_cash", "Net Increase/(Decrease) in Cash",
               [r"net\s+increase.*cash", r"net\s+\(?decrease\)?.*cash"]),
    SchemaItem("opening_cash", "Cash and Cash Equivalents at Beginning of Year",
               [r"cash\s+and\s+cash\s+equivalents?\s+at\s+the?\s*beginning"]),
    SchemaItem("closing_cash", "Cash and Cash Equivalents at End of Year",
               [r"cash\s+and\s+cash\s+equivalents?\s+at\s+the?\s*end"]),
]

SCHEMAS = {
    "balance_sheet": BALANCE_SHEET_SCHEMA,
    "profit_and_loss": PROFIT_AND_LOSS_SCHEMA,
    "cash_flow": CASH_FLOW_SCHEMA,
}

STATEMENT_DISPLAY_NAMES = {
    "balance_sheet": "Balance Sheet",
    "profit_and_loss": "Statement of Profit and Loss",
    "cash_flow": "Cash Flow Statement",
}
