"""Streamlit demo: upload an annual report PDF/image, preview extracted
statements, download the organized Excel workbook.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import os
import sys
import tempfile

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from arx.pipeline import run_pipeline  # noqa: E402
from arx.standardize.schema import STATEMENT_DISPLAY_NAMES  # noqa: E402

st.set_page_config(page_title="Annual Report Extractor", layout="wide")

st.title("Annual Report Extractor")
st.caption(
    "Upload an annual report (PDF) or a photographed financial statement page (JPG/PNG). "
    "The tool locates the Balance Sheet, Statement of Profit & Loss, and Cash Flow Statement, "
    "extracts the line items, and maps them onto a standard schema."
)

with st.sidebar:
    st.header("Options")
    force_ocr = st.checkbox("Force OCR", value=False, help="Use this if the PDF has a text layer but it's garbled.")
    dpi = st.slider("OCR DPI", min_value=150, max_value=500, value=300, step=50)
    st.markdown("---")
    st.markdown(
        "**How it works**\n\n"
        "1. Detect whether the PDF has a real text layer or needs OCR\n"
        "2. Score every page for Balance Sheet / P&L / Cash Flow keyword & line-item density\n"
        "3. Parse the winning pages' tables into (label, values) rows\n"
        "4. Map raw labels onto a canonical Schedule III-style schema\n"
        "5. Export everything (standardized + raw + unmapped) to Excel"
    )

uploaded = st.file_uploader("Upload annual report", type=["pdf", "jpg", "jpeg", "png"])

if uploaded is not None:
    suffix = os.path.splitext(uploaded.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_in:
        tmp_in.write(uploaded.read())
        input_path = tmp_in.name

    output_path = os.path.join(tempfile.gettempdir(), f"{os.path.splitext(uploaded.name)[0]}_extracted.xlsx")

    with st.spinner("Extracting..."):
        try:
            result = run_pipeline(input_path, output_path=output_path, force_ocr=force_ocr, dpi=dpi)
        except Exception as e:
            st.error(f"Extraction failed: {e}")
            st.stop()

    st.success(
        f"Processed {result.page_count} page(s)"
        f"{' via OCR' if result.used_ocr else ' (text layer)'}."
    )

    with open(output_path, "rb") as f:
        st.download_button(
            "Download Excel workbook",
            data=f.read(),
            file_name=os.path.basename(output_path),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    tabs = st.tabs([STATEMENT_DISPLAY_NAMES[k] for k in result.tables.keys()])
    for tab, (key, tables) in zip(tabs, result.tables.items()):
        with tab:
            summary = result.statement_summaries[key]
            if not summary.pages_found:
                st.warning("Not found in this document.")
                continue
            st.caption(
                f"Pages: {summary.pages_found} • "
                f"{summary.rows_extracted} rows extracted • "
                f"{summary.rows_standardized} standardized • "
                f"{summary.rows_unmapped} unmapped"
            )
            st.subheader("Standardized")
            st.dataframe(tables["standardized"], use_container_width=True)
            with st.expander("Raw extracted rows"):
                st.dataframe(tables["raw"], use_container_width=True)
            with st.expander("Unmapped rows (didn't match the schema)"):
                st.dataframe(tables["unmapped"], use_container_width=True)
else:
    st.info("Upload a PDF or image to get started.")
