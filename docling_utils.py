"""Shared document parsing helpers (Docling + PDFplumber + LiteParse)."""

from __future__ import annotations

import json
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pdfplumber
import streamlit as st
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import (
    DocumentConverter,
    ImageFormatOption,
    PdfFormatOption,
)
from liteparse import LiteParse

METHOD_DOCLING = "Docling"
METHOD_PDFPLUMBER = "PDFplumber"
METHOD_LITEPARSE = "LiteParse"
PARSING_METHODS = [METHOD_DOCLING, METHOD_PDFPLUMBER, METHOD_LITEPARSE]

SUPPORTED_EXTENSIONS = [
    "pdf",
    "pptx",
    "ppt",
    "docx",
    "doc",
    "xlsx",
    "xls",
    "csv",
    "txt",
    "json",
    "md",
    "html",
    "htm",
    "png",
    "jpg",
    "jpeg",
    "tif",
    "tiff",
    "bmp",
    "webp",
]

SUPPORTED_EXTENSIONS_SET = set(SUPPORTED_EXTENSIONS)
PDFPLUMBER_EXTENSIONS = ["pdf"]
# LiteParse: PDF, modern Office (LibreOffice may be needed), and images.
LITEPARSE_EXTENSIONS = [
    "pdf",
    "docx",
    "xlsx",
    "pptx",
    "png",
    "jpg",
    "jpeg",
    "tif",
    "tiff",
    "bmp",
    "webp",
]
LITEPARSE_EXTENSIONS_SET = set(LITEPARSE_EXTENSIONS)


@st.cache_resource(show_spinner=False)
def get_converter(enable_ocr: bool) -> DocumentConverter:
    """Build a cached DocumentConverter with optional OCR for PDFs/images."""
    pdf_options = PdfPipelineOptions(
        do_ocr=enable_ocr,
        do_table_structure=True,
    )
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=pdf_options),
        },
    )


@st.cache_resource(show_spinner=False)
def get_liteparse(enable_ocr: bool, liteparse_format: str) -> LiteParse:
    """Build a cached LiteParse instance."""
    return LiteParse(
        ocr_enabled=enable_ocr,
        output_format=liteparse_format,
        quiet=True,
    )


def file_extension(name: str) -> str:
    return Path(name).suffix.lstrip(".").lower()


def is_supported_file(name: str, method: str = METHOD_DOCLING) -> bool:
    ext = file_extension(name)
    if method == METHOD_PDFPLUMBER:
        return ext == "pdf"
    if method == METHOD_LITEPARSE:
        return ext in LITEPARSE_EXTENSIONS_SET
    return ext in SUPPORTED_EXTENSIONS_SET


def methods_for_file(name: str) -> list[str]:
    """Return parsing methods allowed for this file type."""
    ext = file_extension(name)
    methods: list[str] = []
    if ext in SUPPORTED_EXTENSIONS_SET:
        methods.append(METHOD_DOCLING)
    if ext == "pdf":
        methods.append(METHOD_PDFPLUMBER)
    if ext in LITEPARSE_EXTENSIONS_SET:
        methods.append(METHOD_LITEPARSE)
    return methods or [METHOD_DOCLING]


def default_method_for_file(name: str, default_pdf_method: str = METHOD_DOCLING) -> str:
    """Pick a sensible default method for a file."""
    allowed = methods_for_file(name)
    if default_pdf_method in allowed:
        return default_pdf_method
    return allowed[0]


def coerce_method_for_file(name: str, method: str) -> str:
    """Force an invalid method choice back to a valid one for the file."""
    allowed = methods_for_file(name)
    return method if method in allowed else allowed[0]


def allowed_extensions_for_method(method: str) -> list[str]:
    if method == METHOD_PDFPLUMBER:
        return PDFPLUMBER_EXTENSIONS
    if method == METHOD_LITEPARSE:
        return LITEPARSE_EXTENSIONS
    return SUPPORTED_EXTENSIONS


def _table_to_markdown(table: list[list[Any]] | None) -> str:
    if not table:
        return ""
    normalized = [
        [("" if cell is None else str(cell).replace("\n", " ").strip()) for cell in row]
        for row in table
        if row is not None
    ]
    if not normalized:
        return ""
    width = max(len(row) for row in normalized)
    rows = [row + [""] * (width - len(row)) for row in normalized]
    header = rows[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _parse_with_pdfplumber(name: str, raw: bytes, output_format: str) -> tuple[str, str, str]:
    if file_extension(name) != "pdf":
        raise ValueError("PDFplumber only supports PDF files (.pdf).")

    stem = Path(name).stem
    pages_payload: list[dict[str, Any]] = []
    md_parts = [f"# {Path(name).name}", ""]

    with pdfplumber.open(BytesIO(raw)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            pages_payload.append(
                {
                    "page": index,
                    "width": page.width,
                    "height": page.height,
                    "text": text,
                    "tables": tables,
                }
            )
            md_parts.append(f"## Page {index}")
            md_parts.append("")
            if text.strip():
                md_parts.append(text.strip())
                md_parts.append("")
            for t_index, table in enumerate(tables, start=1):
                md_parts.append(f"### Table {t_index}")
                md_parts.append("")
                md_table = _table_to_markdown(table)
                if md_table:
                    md_parts.append(md_table)
                    md_parts.append("")

    if output_format == "Markdown":
        content = "\n".join(md_parts).rstrip() + "\n"
        return content, f"{stem}.md", "text/markdown"

    payload = {
        "source": name,
        "parser": "pdfplumber",
        "page_count": len(pages_payload),
        "pages": pages_payload,
    }
    content = json.dumps(payload, indent=2, ensure_ascii=False)
    return content, f"{stem}.json", "application/json"


def _parse_with_liteparse(
    name: str,
    raw: bytes,
    *,
    enable_ocr: bool,
    output_format: str,
) -> tuple[str, str, str]:
    ext = file_extension(name)
    if ext not in LITEPARSE_EXTENSIONS_SET:
        raise ValueError(
            "LiteParse supports PDF, DOCX/XLSX/PPTX, and common image formats only."
        )

    liteparse_format = "markdown" if output_format == "Markdown" else "json"
    parser = get_liteparse(enable_ocr=enable_ocr, liteparse_format=liteparse_format)

    # Keep the original suffix so LiteParse can detect the format from path.
    suffix = Path(name).suffix if Path(name).suffix else f".{ext}"
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        result = parser.parse(tmp_path)
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    stem = Path(name).stem
    text = result.text or ""
    if output_format == "Markdown":
        return text, f"{stem}.md", "text/markdown"

    try:
        json.loads(text)
        content = text
    except Exception:
        content = json.dumps(
            {
                "source": name,
                "parser": "liteparse",
                "total_pages": getattr(result, "total_pages", None),
                "text": text,
            },
            indent=2,
            ensure_ascii=False,
        )
    return content, f"{stem}.json", "application/json"


def _convert_with_docling(name: str, raw: bytes, enable_ocr: bool):
    converter = get_converter(enable_ocr)
    ext = file_extension(name)

    if ext == "json":
        try:
            source = DocumentStream(name=name, stream=BytesIO(raw))
            return converter.convert(source)
        except Exception:
            try:
                payload = json.loads(raw.decode("utf-8"))
                text = json.dumps(payload, indent=2, ensure_ascii=False)
            except Exception:
                text = raw.decode("utf-8", errors="replace")
            wrapped = f"# {name}\n\n```json\n{text}\n```\n"
            return converter.convert_string(
                content=wrapped,
                format=InputFormat.MD,
                name=Path(name).stem + ".md",
            )

    source = DocumentStream(name=name, stream=BytesIO(raw))
    return converter.convert(source)


def export_docling_result(result, output_format: str) -> tuple[str, str, str]:
    """Return (content, download_name, mime) for a Docling conversion result."""
    stem = result.input.file.stem if result.input and result.input.file else "converted"
    if output_format == "Markdown":
        content = result.document.export_to_markdown()
        return content, f"{stem}.md", "text/markdown"
    data = result.document.export_to_dict()
    content = json.dumps(data, indent=2, ensure_ascii=False)
    return content, f"{stem}.json", "application/json"


def parse_bytes(
    name: str,
    raw: bytes,
    *,
    method: str,
    enable_ocr: bool,
    output_format: str,
) -> tuple[str, str, str]:
    """Parse file bytes with the selected method and return export triple."""
    if method == METHOD_PDFPLUMBER:
        return _parse_with_pdfplumber(name, raw, output_format)
    if method == METHOD_LITEPARSE:
        return _parse_with_liteparse(
            name,
            raw,
            enable_ocr=enable_ocr,
            output_format=output_format,
        )
    if method != METHOD_DOCLING:
        raise ValueError(f"Unknown parsing method: {method}")
    result = _convert_with_docling(name, raw, enable_ocr)
    return export_docling_result(result, output_format)


def parse_upload(
    uploaded_file: Any,
    *,
    method: str,
    enable_ocr: bool,
    output_format: str,
) -> tuple[str, str, str]:
    """Parse an uploaded Streamlit file with the selected method."""
    return parse_bytes(
        uploaded_file.name,
        uploaded_file.getvalue(),
        method=method,
        enable_ocr=enable_ocr,
        output_format=output_format,
    )


# Backwards-compatible aliases used by older page code.
def convert_bytes(name: str, raw: bytes, enable_ocr: bool):
    return _convert_with_docling(name, raw, enable_ocr)


def convert_upload(uploaded_file: Any, enable_ocr: bool):
    return convert_bytes(uploaded_file.name, uploaded_file.getvalue(), enable_ocr)


def export_result(result, output_format: str) -> tuple[str, str, str]:
    return export_docling_result(result, output_format)


def output_name_for_source(source_name: str, output_format: str) -> str:
    """Map an input relative path to an output filename inside a ZIP."""
    path = Path(source_name)
    suffix = ".md" if output_format == "Markdown" else ".json"
    return str(path.with_suffix(suffix)).replace("\\", "/")


def render_parse_settings(*, key_prefix: str = "") -> dict[str, Any]:
    """Render shared sidebar parse settings; return selected options."""
    st.header("Settings")
    method = st.selectbox(
        "Parsing method",
        options=PARSING_METHODS,
        index=0,
        key=f"{key_prefix}parsing_method",
        help=(
            "Docling: multi-format understanding. "
            "PDFplumber: PDF text/tables only. "
            "LiteParse: fast local PDF/Office/image parsing "
            "(https://github.com/run-llama/liteparse)."
        ),
    )
    ocr_methods = {METHOD_DOCLING, METHOD_LITEPARSE}
    enable_ocr = st.checkbox(
        "Enable OCR",
        value=True,
        disabled=method not in ocr_methods,
        help="Applies to Docling and LiteParse (scanned PDFs and images).",
        key=f"{key_prefix}enable_ocr",
    )
    output_format = st.radio(
        "Output format",
        options=["Markdown", "JSON"],
        index=0,
        key=f"{key_prefix}output_format",
    )
    if method == METHOD_PDFPLUMBER:
        st.caption("PDFplumber supports **PDF only**.")
    elif method == METHOD_LITEPARSE:
        st.caption(
            "LiteParse: PDF, DOCX/XLSX/PPTX, and images "
            "([run-llama/liteparse](https://github.com/run-llama/liteparse)). "
            "Office conversion may require LibreOffice."
        )
    else:
        st.caption(
            "Docling: PDF, PPT/PPTX, DOC/DOCX, XLS/XLSX, CSV, TXT, JSON, MD, HTML, images."
        )
    st.markdown("---")
    return {
        "method": method,
        "enable_ocr": enable_ocr,
        "output_format": output_format,
    }
