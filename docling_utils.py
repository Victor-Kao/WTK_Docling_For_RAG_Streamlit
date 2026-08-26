"""Shared document parsing helpers (Docling, PDFplumber, LiteParse, PyMuPDF)."""

from __future__ import annotations

import json
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pdfplumber
import pymupdf
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
METHOD_PYMUPDF = "PyMuPDF"
METHOD_HYBRID = "Hybrid"
METHOD_AUTO = "Auto Selection"
PARSING_METHODS = [
    METHOD_DOCLING,
    METHOD_PDFPLUMBER,
    METHOD_LITEPARSE,
    METHOD_PYMUPDF,
    METHOD_HYBRID,
]
DEFAULT_DOCUMENT_METHODS = [METHOD_AUTO, *PARSING_METHODS]
# Large PDFs default to PyMuPDF (as Hybrid base) under Auto Selection.
AUTO_PDF_SIZE_LIMIT_BYTES = 5 * 1024 * 1024

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
LITEPARSE_NATIVE_EXTENSIONS = [
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "tif",
    "tiff",
    "bmp",
    "webp",
]
# Office / spreadsheet formats need LibreOffice (soffice) for PDF conversion.
LITEPARSE_OFFICE_EXTENSIONS = [
    "docx",
    "doc",
    "xlsx",
    "xls",
    "pptx",
    "ppt",
    "csv",
]
LITEPARSE_NATIVE_EXTENSIONS_SET = set(LITEPARSE_NATIVE_EXTENSIONS)
LITEPARSE_OFFICE_EXTENSIONS_SET = set(LITEPARSE_OFFICE_EXTENSIONS)

_LIBREOFFICE_CANDIDATES = [
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
]


def libreoffice_available() -> bool:
    """True when soffice/LibreOffice is on PATH or in a common Windows install path."""
    if shutil.which("soffice") or shutil.which("libreoffice"):
        return True
    return any(path.is_file() for path in _LIBREOFFICE_CANDIDATES)


def liteparse_extensions() -> list[str]:
    """Formats LiteParse can handle with the current system tools."""
    exts = list(LITEPARSE_NATIVE_EXTENSIONS)
    if libreoffice_available():
        exts.extend(LITEPARSE_OFFICE_EXTENSIONS)
    return exts


def liteparse_extensions_set() -> set[str]:
    return set(liteparse_extensions())


PYMUPDF_EXTENSIONS = [
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "tif",
    "tiff",
    "bmp",
]
PYMUPDF_EXTENSIONS_SET = set(PYMUPDF_EXTENSIONS)
HYBRID_EXTENSIONS = ["pdf"]
HYBRID_EXTENSIONS_SET = set(HYBRID_EXTENSIONS)


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
        return ext in liteparse_extensions_set()
    if method == METHOD_PYMUPDF:
        return ext in PYMUPDF_EXTENSIONS_SET
    if method == METHOD_HYBRID:
        return ext in HYBRID_EXTENSIONS_SET
    return ext in SUPPORTED_EXTENSIONS_SET


def methods_for_file(name: str) -> list[str]:
    """Return parsing methods allowed for this file type."""
    ext = file_extension(name)
    methods: list[str] = []
    if ext in SUPPORTED_EXTENSIONS_SET:
        methods.append(METHOD_DOCLING)
    if ext == "pdf":
        methods.append(METHOD_PDFPLUMBER)
    if ext in liteparse_extensions_set():
        methods.append(METHOD_LITEPARSE)
    if ext in PYMUPDF_EXTENSIONS_SET:
        methods.append(METHOD_PYMUPDF)
    if ext in HYBRID_EXTENSIONS_SET:
        methods.append(METHOD_HYBRID)
    return methods or [METHOD_DOCLING]


def hybrid_base_method_for_pdf(size_bytes: int = 0) -> str:
    """Default engine for Hybrid non-table content / no-table PDFs."""
    if size_bytes > AUTO_PDF_SIZE_LIMIT_BYTES:
        return METHOD_PYMUPDF
    if "pdf" in liteparse_extensions_set():
        return METHOD_LITEPARSE
    return METHOD_PYMUPDF


def auto_method_for_file(name: str, size_bytes: int = 0) -> str:
    """
    Auto Selection defaults:
    - PDF → Hybrid (fast base parser; Docling only on pages with tables)
    - otherwise prefer LiteParse when supported, else Docling
    """
    allowed = methods_for_file(name)
    ext = file_extension(name)
    if ext == "pdf" and METHOD_HYBRID in allowed:
        return METHOD_HYBRID
    if METHOD_LITEPARSE in allowed:
        return METHOD_LITEPARSE
    if METHOD_DOCLING in allowed:
        return METHOD_DOCLING
    return allowed[0]


def default_method_for_file(
    name: str,
    default_document_method: str = METHOD_AUTO,
    size_bytes: int = 0,
) -> str:
    """Pick a sensible default method for a file."""
    if default_document_method == METHOD_AUTO:
        return auto_method_for_file(name, size_bytes=size_bytes)
    allowed = methods_for_file(name)
    if default_document_method in allowed:
        return default_document_method
    return allowed[0]


def coerce_method_for_file(name: str, method: str) -> str:
    """Force an invalid method choice back to a valid one for the file."""
    allowed = methods_for_file(name)
    return method if method in allowed else allowed[0]


def allowed_extensions_for_method(method: str) -> list[str]:
    if method == METHOD_PDFPLUMBER:
        return PDFPLUMBER_EXTENSIONS
    if method == METHOD_LITEPARSE:
        return liteparse_extensions()
    if method == METHOD_PYMUPDF:
        return PYMUPDF_EXTENSIONS
    if method == METHOD_HYBRID:
        return HYBRID_EXTENSIONS
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


def _parse_with_pymupdf(name: str, raw: bytes, output_format: str) -> tuple[str, str, str]:
    ext = file_extension(name)
    if ext not in PYMUPDF_EXTENSIONS_SET:
        raise ValueError("PyMuPDF supports PDF and common image formats in this app.")

    stem = Path(name).stem
    filetype = ext if ext != "jpg" else "jpeg"
    doc = pymupdf.open(stream=raw, filetype=filetype)
    try:
        pages_payload: list[dict[str, Any]] = []
        md_parts = [f"# {Path(name).name}", ""]
        for index, page in enumerate(doc, start=1):
            # Prefer markdown text mode when available; fall back to plain text.
            try:
                text = page.get_text("markdown") or ""
            except Exception:
                text = page.get_text("text") or ""
            pages_payload.append({"page": index, "text": text})
            md_parts.append(f"## Page {index}")
            md_parts.append("")
            if text.strip():
                md_parts.append(text.strip())
                md_parts.append("")
    finally:
        doc.close()

    if output_format == "Markdown":
        content = "\n".join(md_parts).rstrip() + "\n"
        return content, f"{stem}.md", "text/markdown"

    payload = {
        "source": name,
        "parser": "pymupdf",
        "page_count": len(pages_payload),
        "pages": pages_payload,
    }
    content = json.dumps(payload, indent=2, ensure_ascii=False)
    return content, f"{stem}.json", "application/json"


def _pdf_pages_with_tables(raw: bytes) -> set[int]:
    """Return 0-based page indexes that appear to contain tables (pdfplumber)."""
    table_pages: set[int] = set()
    with pdfplumber.open(BytesIO(raw)) as pdf:
        for index, page in enumerate(pdf.pages):
            try:
                found = page.find_tables() or []
            except Exception:
                found = []
            if found:
                table_pages.add(index)
                continue
            try:
                extracted = page.extract_tables() or []
            except Exception:
                extracted = []
            if any(extracted):
                table_pages.add(index)
    return table_pages


def _pymupdf_page_text(page) -> str:
    try:
        return page.get_text("markdown") or ""
    except Exception:
        return page.get_text("text") or ""


def _docling_single_page_pdf(
    source_name: str,
    page_raw: bytes,
    page_number: int,
    *,
    enable_ocr: bool,
) -> str:
    """Convert one PDF page with Docling and return markdown (without wrapping title)."""
    page_name = f"{Path(source_name).stem}_p{page_number}.pdf"
    result = _convert_with_docling(page_name, page_raw, enable_ocr)
    return (result.document.export_to_markdown() or "").strip()


def _parse_with_hybrid(
    name: str,
    raw: bytes,
    *,
    enable_ocr: bool,
    output_format: str,
) -> tuple[str, str, str]:
    """
    Hybrid PDF parsing:
    - No tables → LiteParse (≤5 MB) or PyMuPDF (>5 MB)
    - Pages with tables → Docling for those pages only
    - Other pages → PyMuPDF text
    """
    if file_extension(name) != "pdf":
        raise ValueError("Hybrid mode supports PDF files only.")

    stem = Path(name).stem
    base_method = hybrid_base_method_for_pdf(len(raw))
    table_pages = _pdf_pages_with_tables(raw)

    if not table_pages:
        content, download_name, mime = parse_bytes(
            name,
            raw,
            method=base_method,
            enable_ocr=enable_ocr,
            output_format=output_format,
        )
        if output_format == "JSON":
            try:
                payload = json.loads(content)
            except Exception:
                payload = {"text": content}
            if not isinstance(payload, dict):
                payload = {"data": payload}
            payload["parser"] = "hybrid"
            payload["hybrid"] = {
                "base_method": base_method,
                "table_pages": [],
                "mode": "base_only",
            }
            content = json.dumps(payload, indent=2, ensure_ascii=False)
        return content, download_name, mime

    doc = pymupdf.open(stream=raw, filetype="pdf")
    pages_payload: list[dict[str, Any]] = []
    md_parts = [f"# {Path(name).name}", ""]
    try:
        for index in range(len(doc)):
            page_number = index + 1
            md_parts.append(f"## Page {page_number}")
            md_parts.append("")
            if index in table_pages:
                single = pymupdf.open()
                try:
                    single.insert_pdf(doc, from_page=index, to_page=index)
                    page_raw = single.tobytes()
                finally:
                    single.close()
                try:
                    text = _docling_single_page_pdf(
                        name,
                        page_raw,
                        page_number,
                        enable_ocr=enable_ocr,
                    )
                    engine = "docling"
                except Exception as exc:
                    text = _pymupdf_page_text(doc[index])
                    engine = "pymupdf_fallback"
                    text = (
                        f"_Docling failed on this table page ({exc}); "
                        f"fell back to PyMuPDF._\n\n{text}"
                    ).strip()
            else:
                text = _pymupdf_page_text(doc[index])
                engine = "pymupdf"
            pages_payload.append(
                {
                    "page": page_number,
                    "engine": engine,
                    "has_table": index in table_pages,
                    "text": text,
                }
            )
            if text.strip():
                md_parts.append(text.strip())
                md_parts.append("")
    finally:
        doc.close()

    if output_format == "Markdown":
        content = "\n".join(md_parts).rstrip() + "\n"
        return content, f"{stem}.md", "text/markdown"

    payload = {
        "source": name,
        "parser": "hybrid",
        "hybrid": {
            "base_method": base_method,
            "table_pages": [p + 1 for p in sorted(table_pages)],
            "mode": "page_hybrid",
        },
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
    allowed = liteparse_extensions_set()
    if ext not in allowed:
        if ext in LITEPARSE_OFFICE_EXTENSIONS_SET and not libreoffice_available():
            raise ValueError(
                "LiteParse needs LibreOffice to parse Office/spreadsheet files "
                "(DOCX/PPTX/XLSX/CSV). Install LibreOffice, or use Docling for those formats."
            )
        raise ValueError(
            "LiteParse supports PDF and images natively; Office formats need LibreOffice."
        )

    liteparse_format = "markdown" if output_format == "Markdown" else "json"
    parser = get_liteparse(enable_ocr=enable_ocr, liteparse_format=liteparse_format)

    suffix = Path(name).suffix if Path(name).suffix else f".{ext}"
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        result = parser.parse(tmp_path)
    except Exception as exc:
        message = str(exc).lower()
        if "libreoffice" in message:
            raise RuntimeError(
                "LiteParse could not convert this Office file because LibreOffice "
                "is missing. Install LibreOffice (see README), or parse with Docling."
            ) from exc
        raise
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
    if method == METHOD_PYMUPDF:
        return _parse_with_pymupdf(name, raw, output_format)
    if method == METHOD_HYBRID:
        return _parse_with_hybrid(
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
            "Docling / LiteParse: multi-format. "
            "PDFplumber / PyMuPDF: PDF-focused. "
            "Hybrid (PDF): default parser, Docling only on pages with tables."
        ),
    )
    ocr_methods = {METHOD_DOCLING, METHOD_LITEPARSE, METHOD_HYBRID}
    enable_ocr = st.checkbox(
        "Enable OCR",
        value=True,
        disabled=method not in ocr_methods,
        help="Applies to Docling, LiteParse, and Hybrid (Docling table pages).",
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
        if libreoffice_available():
            st.caption(
                "LiteParse: PDF, images, and Office/spreadsheets via LibreOffice "
                "([run-llama/liteparse](https://github.com/run-llama/liteparse))."
            )
        else:
            st.caption(
                "LiteParse: **PDF and images only** on this machine. "
                "PPTX / XLSX / CSV / DOCX need **LibreOffice** "
                "([install guide](https://www.libreoffice.org/download/download-libreoffice/)); "
                "use **Docling** for those formats until then."
            )
    elif method == METHOD_PYMUPDF:
        st.caption(
            "PyMuPDF: PDF and common images "
            "([pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF))."
        )
    elif method == METHOD_HYBRID:
        st.caption(
            "**Hybrid (PDF only):** parse with LiteParse / PyMuPDF by default; "
            "pages with detected tables use **Docling**, then continue with the fast parser."
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
