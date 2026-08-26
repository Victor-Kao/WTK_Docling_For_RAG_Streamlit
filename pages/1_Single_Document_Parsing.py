"""
Single-document parsing with Docling, PDFplumber, or LiteParse.
"""

from __future__ import annotations

import json

import streamlit as st

from docling_utils import (
    METHOD_HYBRID,
    METHOD_LITEPARSE,
    METHOD_PDFPLUMBER,
    METHOD_PYMUPDF,
    allowed_extensions_for_method,
    file_extension,
    parse_upload,
    render_parse_settings,
)

st.set_page_config(
    page_title="Single Document Parsing | Documents Parsing Tool",
    page_icon="📄",
    layout="wide",
)

TEXT_LIKE_EXTENSIONS = {"txt", "json", "md", "html", "htm", "csv"}

st.title("Single Document Parsing")
st.markdown(
    "Upload a supported file and convert it with "
    "[Docling](https://github.com/docling-project/docling), "
    "[PDFplumber](https://github.com/jsvine/pdfplumber), "
    "[LiteParse](https://github.com/run-llama/liteparse), "
    "[PyMuPDF](https://github.com/pymupdf/PyMuPDF), or "
    "**Hybrid** (PDF: fast parser + Docling on table pages)."
)

if "conversion" not in st.session_state:
    st.session_state.conversion = None
if "show_result" not in st.session_state:
    st.session_state.show_result = True

with st.sidebar:
    settings = render_parse_settings(key_prefix="single_")

method = settings["method"]
enable_ocr = settings["enable_ocr"]
output_format = settings["output_format"]
allowed_types = allowed_extensions_for_method(method)

uploaded = st.file_uploader(
    "Choose a file",
    type=allowed_types,
    help=(
        "PDF only when PDFplumber or Hybrid is selected."
        if method in {METHOD_PDFPLUMBER, METHOD_HYBRID}
        else (
            "PDF and images when PyMuPDF is selected."
            if method == METHOD_PYMUPDF
            else (
                "PDF and images when LiteParse is selected "
                "(Office/CSV need LibreOffice)."
                if method == METHOD_LITEPARSE
                else "Select one document to convert."
            )
        )
    ),
    key=f"single_uploader_{method}",
)

if uploaded is not None:
    ext = file_extension(uploaded.name)
    size_kb = len(uploaded.getvalue()) / 1024
    st.write(
        f"**File:** `{uploaded.name}` · **Size:** {size_kb:.1f} KB · **Method:** {method}"
    )

    if ext in {"png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"}:
        st.image(uploaded.getvalue(), caption=uploaded.name, use_container_width=True)
    elif ext in TEXT_LIKE_EXTENSIONS and size_kb < 500:
        try:
            preview = uploaded.getvalue().decode("utf-8", errors="replace")
            st.text_area("Input preview", preview[:5000], height=180)
        except Exception:
            pass

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        convert_clicked = st.button("Convert", type="primary", use_container_width=True)
    with col_b:
        if st.button("Clear result", use_container_width=True):
            st.session_state.conversion = None
            st.session_state.show_result = True
            st.rerun()
    with col_c:
        has_result = (
            st.session_state.conversion is not None
            and st.session_state.conversion.get("source_name") == uploaded.name
        )
        toggle_label = (
            "Hide result" if st.session_state.show_result else "Show result"
        )
        if st.button(toggle_label, use_container_width=True, disabled=not has_result):
            st.session_state.show_result = not st.session_state.show_result
            st.rerun()

    if convert_clicked:
        with st.spinner(f"Converting `{uploaded.name}` with {method}…"):
            try:
                content, download_name, mime = parse_upload(
                    uploaded,
                    method=method,
                    enable_ocr=enable_ocr,
                    output_format=output_format,
                )
                st.session_state.conversion = {
                    "source_name": uploaded.name,
                    "output_format": output_format,
                    "method": method,
                    "content": content,
                    "download_name": download_name,
                    "mime": mime,
                }
                st.session_state.show_result = True
            except Exception as exc:
                st.session_state.conversion = None
                st.error(f"Conversion failed: {exc}")

    conv = st.session_state.conversion
    if conv and conv.get("source_name") == uploaded.name:
        st.success(f"Conversion completed with **{conv.get('method', method)}**.")
        st.download_button(
            label=f"Download {conv['output_format']}",
            data=conv["content"],
            file_name=conv["download_name"],
            mime=conv["mime"],
        )
        if st.session_state.show_result:
            st.subheader("Preview")
            if conv["output_format"] == "JSON":
                st.json(json.loads(conv["content"]))
            else:
                st.markdown(conv["content"])
        else:
            st.info("Converted result is hidden. Click **Show result** to display it.")
else:
    st.session_state.conversion = None
    st.session_state.show_result = True
    st.info("Upload a file above to begin.")
