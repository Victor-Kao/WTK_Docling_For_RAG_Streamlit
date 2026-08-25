"""
Bulk-parse an uploaded folder with per-file Docling / PDFplumber methods.
"""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from docling_utils import (
    METHOD_DOCLING,
    PARSING_METHODS,
    SUPPORTED_EXTENSIONS,
    coerce_method_for_file,
    default_method_for_file,
    is_supported_file,
    output_name_for_source,
    parse_bytes,
)

st.set_page_config(
    page_title="Bulk Parsing | Documents Parsing Tool",
    page_icon="📁",
    layout="wide",
)

STATUS_PENDING = "Pending"
STATUS_IN_PROGRESS = "In progress"
STATUS_DONE = "Done"
STATUS_FAILED = "Failed"
PREVIEW_NONE = "None"

STATUS_COLORS = {
    STATUS_PENDING: "⚪",
    STATUS_IN_PROGRESS: "🔄",
    STATUS_DONE: "✅",
    STATUS_FAILED: "❌",
}


def _init_state() -> None:
    defaults = {
        "bulk_jobs": None,
        "bulk_results": {},
        "bulk_running": False,
        "bulk_finished": False,
        "bulk_output_format_used": "Markdown",
        "bulk_methods_df": None,
        "bulk_methods_editor_version": 0,
        "bulk_include_df": None,
        "bulk_include_editor_version": 0,
        "bulk_selection_committed": False,
        "bulk_zip_bytes": None,
        "bulk_zip_file_count": 0,
        "bulk_uploader_version": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_bulk() -> None:
    st.session_state.bulk_jobs = None
    st.session_state.bulk_results = {}
    st.session_state.bulk_running = False
    st.session_state.bulk_finished = False
    st.session_state.bulk_output_format_used = "Markdown"
    st.session_state.bulk_methods_df = None
    st.session_state.bulk_methods_editor_version = 0
    st.session_state.bulk_include_df = None
    st.session_state.bulk_include_editor_version = 0
    st.session_state.bulk_selection_committed = False
    st.session_state.bulk_zip_bytes = None
    st.session_state.bulk_zip_file_count = 0


def _detect_files(
    uploaded_files: list,
    default_pdf_method: str,
    existing_jobs: list[dict] | None = None,
) -> list[dict]:
    previous = {j["file"]: j.get("method") for j in (existing_jobs or [])}
    jobs: list[dict] = []
    seen: set[str] = set()
    for f in uploaded_files:
        name = f.name.replace("\\", "/")
        if name in seen or not is_supported_file(name, method=METHOD_DOCLING):
            continue
        seen.add(name)
        prior = previous.get(name)
        method = coerce_method_for_file(
            name,
            prior
            if prior
            else default_method_for_file(name, default_pdf_method=default_pdf_method),
        )
        jobs.append(
            {
                "file": name,
                "method": method,
                "status": STATUS_PENDING,
                "detail": "",
                "size_kb": round(len(f.getvalue()) / 1024, 1),
            }
        )
    return sorted(jobs, key=lambda j: j["file"].lower())


def _methods_dataframe(jobs: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "File": j["file"],
                "Method": j["method"],
                "Size (KB)": j["size_kb"],
            }
            for j in jobs
        ],
        columns=["File", "Method", "Size (KB)"],
    )


def _status_dataframe(jobs: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Status": f"{STATUS_COLORS.get(j['status'], '')} {j['status']}",
                "File": j["file"],
                "Method": j["method"],
                "Size (KB)": j["size_kb"],
                "Detail": j["detail"],
            }
            for j in jobs
        ],
        columns=["Status", "File", "Method", "Size (KB)", "Detail"],
    )


def _include_dataframe(successful: list[str], results: dict[str, dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Include in ZIP": True,
                "Source file": source,
                "Output in ZIP": results[source]["out_name"],
                "Method": results[source]["method"],
            }
            for source in successful
        ],
        columns=["Include in ZIP", "Source file", "Output in ZIP", "Method"],
    )


def _status_counts(jobs: list[dict]) -> Counter:
    return Counter(j["status"] for j in jobs)


def _render_dashboard(
    jobs: list[dict], progress_placeholder, metrics_placeholder, table_placeholder
) -> None:
    counts = _status_counts(jobs)
    total = len(jobs) or 1
    done_like = counts[STATUS_DONE] + counts[STATUS_FAILED]
    progress_placeholder.progress(
        done_like / total,
        text=f"Progress: {done_like}/{len(jobs)} processed",
    )
    m1, m2, m3, m4, m5 = metrics_placeholder.columns(5)
    m1.metric("Total", len(jobs))
    m2.metric("Done", counts[STATUS_DONE])
    m3.metric("In progress", counts[STATUS_IN_PROGRESS])
    m4.metric("Pending", counts[STATUS_PENDING])
    m5.metric("Failed", counts[STATUS_FAILED])
    table_placeholder.dataframe(
        _status_dataframe(jobs),
        use_container_width=True,
        hide_index=True,
    )


def _include_map_from_df(df: pd.DataFrame) -> dict[str, bool]:
    return {
        str(row["Source file"]): bool(row["Include in ZIP"])
        for _, row in df.iterrows()
    }


def _build_zip(results: dict[str, dict], include: dict[str, bool]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for source_name, payload in sorted(results.items()):
            if not include.get(source_name, True):
                continue
            content = payload["content"]
            data = content.encode("utf-8") if isinstance(content, str) else content
            zf.writestr(payload["out_name"], data)
    return buf.getvalue()


def _successful_sources(jobs: list[dict], results: dict[str, dict]) -> list[str]:
    return [
        j["file"]
        for j in jobs
        if j.get("status") == STATUS_DONE and j["file"] in results
    ]


def _apply_methods_from_df(jobs: list[dict], methods_df: pd.DataFrame) -> list[str]:
    """Apply edited methods onto jobs. Returns files that were coerced."""
    method_by_file = {
        str(row["File"]): str(row["Method"]) for _, row in methods_df.iterrows()
    }
    invalid_rows: list[str] = []
    for job in jobs:
        chosen = method_by_file.get(job["file"], job["method"])
        coerced = coerce_method_for_file(job["file"], chosen)
        if coerced != chosen:
            invalid_rows.append(job["file"])
        job["method"] = coerced
    return invalid_rows


def _clear_cache() -> None:
    """Clear Streamlit caches, bulk results, and the uploaded folder widget."""
    st.cache_resource.clear()
    st.cache_data.clear()

    # Force a brand-new file_uploader instance (deleting the key alone is not enough).
    old_uploader_key = f"bulk_folder_uploader_{st.session_state.get('bulk_uploader_version', 0)}"
    for key in list(st.session_state.keys()):
        key_str = str(key)
        if (
            key_str == "bulk_folder_uploader"
            or key_str.startswith("bulk_folder_uploader_")
            or key_str.startswith("bulk_method_editor_")
            or key_str.startswith("bulk_include_editor_")
            or key_str in {"bulk_preview_source", "bulk_zip_selection_form"}
        ):
            del st.session_state[key]

    _reset_bulk()
    st.session_state.bulk_uploader_version = (
        st.session_state.get("bulk_uploader_version", 0) + 1
    )
    st.session_state.bulk_methods_editor_version += 1
    st.session_state.bulk_include_editor_version += 1

    # Ensure the previous uploader key cannot linger after version bump.
    if old_uploader_key in st.session_state:
        del st.session_state[old_uploader_key]


_init_state()

st.title("Bulk Parsing")
st.markdown(
    "Upload a whole folder, choose a parsing method **per file** "
    "(Docling, PDFplumber, or LiteParse), "
    "watch live status, and download a ZIP of successful outputs."
)

with st.sidebar:
    st.header("Settings")
    default_pdf_method = st.selectbox(
        "Default method for PDFs",
        options=PARSING_METHODS,
        index=0,
        key="bulk_default_pdf_method",
        help="Applied to newly detected PDFs. You can override each file below.",
    )
    st.caption(
        "Non-PDF defaults to **Docling**. Images/Office can also use **LiteParse**. "
        "PDFplumber is PDF-only."
    )
    enable_ocr = st.checkbox(
        "Enable OCR (Docling / LiteParse)",
        value=True,
        help="Applies when a file uses Docling or LiteParse.",
        key="bulk_enable_ocr",
    )
    output_format = st.radio(
        "Output format",
        options=["Markdown", "JSON"],
        index=0,
        key="bulk_output_format",
    )
    st.markdown("---")
    st.caption(
        "Folder upload keeps relative paths. "
        "LiteParse: https://github.com/run-llama/liteparse"
    )
    if st.button(
        "Clear cache",
        use_container_width=True,
        disabled=st.session_state.bulk_running,
        help="Clear parser caches, conversion results, and the uploaded folder.",
        key="bulk_clear_cache",
    ):
        _clear_cache()
        st.rerun()

uploaded_files = st.file_uploader(
    "Upload a folder",
    type=SUPPORTED_EXTENSIONS,
    accept_multiple_files="directory",
    help="Select an entire folder. Supported documents will be listed for per-file method selection.",
    key=f"bulk_folder_uploader_{st.session_state.bulk_uploader_version}",
)

if not uploaded_files:
    _reset_bulk()
    st.info("Choose a folder above to detect convertible files.")
    st.stop()

detected_names = tuple(
    sorted(
        {
            f.name.replace("\\", "/")
            for f in uploaded_files
            if is_supported_file(f.name.replace("\\", "/"), method=METHOD_DOCLING)
        }
    )
)
prev_names = tuple(sorted(j["file"] for j in (st.session_state.bulk_jobs or [])))

if (not st.session_state.bulk_running) and (
    st.session_state.bulk_jobs is None or detected_names != prev_names
):
    st.session_state.bulk_jobs = _detect_files(
        uploaded_files,
        default_pdf_method=default_pdf_method,
        existing_jobs=st.session_state.bulk_jobs,
    )
    st.session_state.bulk_results = {}
    st.session_state.bulk_finished = False
    st.session_state.bulk_methods_df = _methods_dataframe(st.session_state.bulk_jobs)
    st.session_state.bulk_methods_editor_version += 1
    st.session_state.bulk_include_df = None
    st.session_state.bulk_include_editor_version += 1
    st.session_state.bulk_selection_committed = False
    st.session_state.bulk_zip_bytes = None
    st.session_state.bulk_zip_file_count = 0

jobs = st.session_state.bulk_jobs or []

st.subheader("Detected files")
if not jobs:
    st.warning("No supported files found in this folder.")
    st.stop()

if st.session_state.bulk_methods_df is None:
    st.session_state.bulk_methods_df = _methods_dataframe(jobs)

st.caption(
    f"Found **{len(jobs)}** supported file(s). "
    "Set **Method** per row: PDFs → Docling / PDFplumber / LiteParse; "
    "images & Office → Docling / LiteParse; other types → Docling."
)

edited_methods = st.data_editor(
    st.session_state.bulk_methods_df,
    use_container_width=True,
    hide_index=True,
    disabled=["File", "Size (KB)"]
    if not st.session_state.bulk_running
    else ["File", "Method", "Size (KB)"],
    column_config={
        "Method": st.column_config.SelectboxColumn(
            "Method",
            help="PDFplumber is PDF-only. LiteParse supports PDF, DOCX/XLSX/PPTX, and images.",
            options=PARSING_METHODS,
            required=True,
        ),
        "File": st.column_config.TextColumn("File", width="large"),
    },
    key=f"bulk_method_editor_{st.session_state.bulk_methods_editor_version}",
)
# Keep a stable snapshot for Start convert / Reset without rewriting every interaction.
# Read live edits from the editor return value only when needed.

col_a, col_b = st.columns(2)
with col_a:
    start = st.button(
        "Start convert",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.bulk_running,
    )
with col_b:
    if st.button("Reset", use_container_width=True, disabled=st.session_state.bulk_running):
        st.session_state.bulk_jobs = _detect_files(
            uploaded_files,
            default_pdf_method=default_pdf_method,
            existing_jobs=None,
        )
        st.session_state.bulk_results = {}
        st.session_state.bulk_finished = False
        st.session_state.bulk_methods_df = _methods_dataframe(st.session_state.bulk_jobs)
        st.session_state.bulk_methods_editor_version += 1
        st.session_state.bulk_include_df = None
        st.session_state.bulk_include_editor_version += 1
        st.session_state.bulk_selection_committed = False
        st.session_state.bulk_zip_bytes = None
        st.session_state.bulk_zip_file_count = 0
        st.rerun()

st.subheader("Live dashboard")
progress_ph = st.empty()
metrics_ph = st.empty()
table_ph = st.empty()
_render_dashboard(jobs, progress_ph, metrics_ph, table_ph)

if start and not st.session_state.bulk_running:
    invalid_rows = _apply_methods_from_df(st.session_state.bulk_jobs, edited_methods)
    # Persist coerced methods into the stable methods dataframe once.
    st.session_state.bulk_methods_df = _methods_dataframe(st.session_state.bulk_jobs)
    st.session_state.bulk_methods_editor_version += 1
    if invalid_rows:
        st.warning(
            "Some method choices were invalid for the file type and were reset "
            "(e.g. PDFplumber is PDF-only): "
            + ", ".join(f"`{name}`" for name in invalid_rows[:8])
            + ("…" if len(invalid_rows) > 8 else "")
        )

    st.session_state.bulk_running = True
    st.session_state.bulk_finished = False
    st.session_state.bulk_results = {}
    st.session_state.bulk_include_df = None
    st.session_state.bulk_selection_committed = False
    st.session_state.bulk_zip_bytes = None
    st.session_state.bulk_zip_file_count = 0
    st.session_state.bulk_output_format_used = output_format

    for job in st.session_state.bulk_jobs:
        job["status"] = STATUS_PENDING
        job["detail"] = ""
        job.pop("out_name", None)

    upload_map = {f.name.replace("\\", "/"): f for f in uploaded_files}

    for job in st.session_state.bulk_jobs:
        file_method = coerce_method_for_file(
            job["file"], job.get("method", METHOD_DOCLING)
        )
        job["method"] = file_method
        job["status"] = STATUS_IN_PROGRESS
        job["detail"] = f"Converting with {file_method}…"
        _render_dashboard(st.session_state.bulk_jobs, progress_ph, metrics_ph, table_ph)

        source_name = job["file"]
        uploaded = upload_map.get(source_name)
        if uploaded is None:
            job["status"] = STATUS_FAILED
            job["detail"] = "File missing from upload set"
            _render_dashboard(st.session_state.bulk_jobs, progress_ph, metrics_ph, table_ph)
            continue

        try:
            content, _, _ = parse_bytes(
                source_name,
                uploaded.getvalue(),
                method=file_method,
                enable_ocr=enable_ocr,
                output_format=output_format,
            )
            out_name = output_name_for_source(source_name, output_format)
            existing_out_names = {
                payload["out_name"] for payload in st.session_state.bulk_results.values()
            }
            if out_name in existing_out_names:
                stem = Path(out_name).stem
                parent = str(Path(out_name).parent).replace("\\", "/")
                suffix = Path(out_name).suffix
                n = 2
                while True:
                    candidate = (
                        f"{parent}/{stem}_{n}{suffix}"
                        if parent != "."
                        else f"{stem}_{n}{suffix}"
                    )
                    if candidate not in existing_out_names:
                        out_name = candidate
                        break
                    n += 1
            st.session_state.bulk_results[source_name] = {
                "out_name": out_name,
                "content": content,
                "method": file_method,
            }
            job["out_name"] = out_name
            job["status"] = STATUS_DONE
            job["detail"] = f"{file_method} → {out_name}"
        except Exception as exc:
            job["status"] = STATUS_FAILED
            job["detail"] = str(exc)

        _render_dashboard(st.session_state.bulk_jobs, progress_ph, metrics_ph, table_ph)

    successful = _successful_sources(
        st.session_state.bulk_jobs or [], st.session_state.bulk_results or {}
    )
    if successful:
        st.session_state.bulk_include_df = _include_dataframe(
            successful, st.session_state.bulk_results
        )
        st.session_state.bulk_include_editor_version += 1
        st.session_state.bulk_selection_committed = False
        st.session_state.bulk_zip_bytes = None
        st.session_state.bulk_zip_file_count = 0

    st.session_state.bulk_running = False
    st.session_state.bulk_finished = True
    st.rerun()

if st.session_state.bulk_finished:
    counts = _status_counts(st.session_state.bulk_jobs or [])
    results = st.session_state.bulk_results or {}
    method_counts = Counter(
        payload.get("method", METHOD_DOCLING) for payload in results.values()
    )
    st.markdown("---")
    if counts[STATUS_DONE] and results:
        method_summary = ", ".join(
            f"**{name}**: {count}" for name, count in sorted(method_counts.items())
        )
        st.success(
            f"Bulk conversion finished: **{counts[STATUS_DONE]}** done, "
            f"**{counts[STATUS_FAILED]}** failed. "
            f"Successful by method — {method_summary}."
        )

        successful = _successful_sources(st.session_state.bulk_jobs or [], results)
        if st.session_state.bulk_include_df is None:
            st.session_state.bulk_include_df = _include_dataframe(successful, results)
            st.session_state.bulk_include_editor_version += 1
            st.session_state.bulk_selection_committed = False
            st.session_state.bulk_zip_bytes = None
            st.session_state.bulk_zip_file_count = 0

        st.subheader("ZIP download selection")
        st.caption(
            "Edit the table without refreshing the page. When done, click "
            "**Finish selection** to confirm, then the download button appears."
        )

        if not st.session_state.bulk_selection_committed:
            with st.form("bulk_zip_selection_form", clear_on_submit=False):
                edited_include = st.data_editor(
                    st.session_state.bulk_include_df,
                    use_container_width=True,
                    hide_index=True,
                    disabled=["Source file", "Output in ZIP", "Method"],
                    column_config={
                        "Include in ZIP": st.column_config.CheckboxColumn(
                            "Include in ZIP",
                            help="Uncheck to exclude this file from the ZIP.",
                            default=True,
                        )
                    },
                    key=f"bulk_include_editor_{st.session_state.bulk_include_editor_version}",
                )
                sel1, sel2, sel3 = st.columns(3)
                with sel1:
                    include_all = st.form_submit_button(
                        "Include all", use_container_width=True
                    )
                with sel2:
                    exclude_all = st.form_submit_button(
                        "Exclude all", use_container_width=True
                    )
                with sel3:
                    finish_selection = st.form_submit_button(
                        "Finish selection",
                        type="primary",
                        use_container_width=True,
                    )

            if include_all:
                df = edited_include.copy()
                df["Include in ZIP"] = True
                st.session_state.bulk_include_df = df
                st.session_state.bulk_include_editor_version += 1
                st.session_state.bulk_selection_committed = False
                st.rerun()
            elif exclude_all:
                df = edited_include.copy()
                df["Include in ZIP"] = False
                st.session_state.bulk_include_df = df
                st.session_state.bulk_include_editor_version += 1
                st.session_state.bulk_selection_committed = False
                st.rerun()
            elif finish_selection:
                include_map = _include_map_from_df(edited_include)
                included_count = sum(1 for selected in include_map.values() if selected)
                st.session_state.bulk_include_df = edited_include.copy()
                if included_count <= 0:
                    st.session_state.bulk_selection_committed = False
                    st.session_state.bulk_zip_bytes = None
                    st.session_state.bulk_zip_file_count = 0
                    st.warning("Select at least one file before finishing.")
                else:
                    st.session_state.bulk_zip_bytes = _build_zip(results, include_map)
                    st.session_state.bulk_zip_file_count = included_count
                    st.session_state.bulk_selection_committed = True
                    st.rerun()
            else:
                st.info("Adjust the checkboxes, then click **Finish selection**.")
        else:
            st.dataframe(
                st.session_state.bulk_include_df,
                use_container_width=True,
                hide_index=True,
            )
            st.write(
                f"**{st.session_state.bulk_zip_file_count}** file(s) confirmed for download."
            )
            if st.session_state.bulk_zip_bytes:
                st.download_button(
                    label=(
                        f"Download ZIP "
                        f"({st.session_state.bulk_zip_file_count} "
                        f"file{'s' if st.session_state.bulk_zip_file_count != 1 else ''})"
                    ),
                    data=st.session_state.bulk_zip_bytes,
                    file_name="bulk_converted.zip",
                    mime="application/zip",
                    type="primary",
                )
            if st.button("Edit selection", use_container_width=False):
                st.session_state.bulk_selection_committed = False
                st.session_state.bulk_zip_bytes = None
                st.session_state.bulk_zip_file_count = 0
                st.session_state.bulk_include_editor_version += 1
                st.rerun()

        st.subheader("Preview converted file")
        preview_options = [PREVIEW_NONE] + successful
        preview_source = st.selectbox(
            "Select one file to preview",
            options=preview_options,
            index=0,
            key="bulk_preview_source",
            help="Choose None to hide the preview. Only one file can be previewed at a time.",
        )
        if preview_source != PREVIEW_NONE and preview_source in results:
            payload = results[preview_source]
            st.caption(
                f"Method: **{payload['method']}** · Output: `{payload['out_name']}`"
            )
            used_format = st.session_state.bulk_output_format_used
            if used_format == "JSON":
                try:
                    st.json(json.loads(payload["content"]))
                except Exception:
                    st.code(payload["content"], language="json")
            else:
                st.markdown(payload["content"])
        else:
            st.caption("No file selected for preview.")
    else:
        st.error("All conversions failed. Fix the errors above and try again.")
