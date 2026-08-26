"""
Documents Parsing Tool — Introduction page.
"""

import streamlit as st

st.set_page_config(
    page_title="Documents Parsing Tool",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Documents Parsing Tool")
st.caption(
    "Parse documents into Markdown / JSON with Docling, PDFplumber, LiteParse, PyMuPDF, or Hybrid."
)

st.markdown("---")

st.header("About this tool")
st.markdown(
    """
This Streamlit app converts documents in the browser, previews results, and supports
single-file or bulk folder workflows.

**Parsing methods**
- **[Docling](https://github.com/docling-project/docling)** — multi-format document
  understanding (PDF, Office, HTML, images, and more), with layout/table recovery and OCR.
- **[PDFplumber](https://github.com/jsvine/pdfplumber)** — detailed PDF text and table
  extraction (PDF only; best on machine-generated PDFs).
- **[LiteParse](https://github.com/run-llama/liteparse)** — fast local parsing for PDF
  and images; Office/spreadsheets (DOCX/PPTX/XLSX/CSV) only if LibreOffice is installed.
- **[PyMuPDF](https://github.com/pymupdf/PyMuPDF)** — high-performance PDF/image text extraction.
- **Hybrid** — PDF only: fast default parser (LiteParse / PyMuPDF), **Docling** only on pages
  that contain tables, then switch back.
"""
)

st.header("Supported input formats")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        """
- **PDF** (`.pdf`)
- **Word** (`.docx`, `.doc`)
- **PowerPoint** (`.pptx`, `.ppt`)
- **Excel** (`.xlsx`, `.xls`)
"""
    )
with col2:
    st.markdown(
        """
- **CSV** (`.csv`)
- **Text** (`.txt`)
- **JSON** (`.json`)
- **Markdown** (`.md`)
"""
    )
with col3:
    st.markdown(
        """
- **HTML** (`.html`, `.htm`)
- **Images** (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`)
"""
    )

st.info(
    "Legacy Office formats (`.doc`, `.ppt`, `.xls`) may require LibreOffice on the host machine. "
    "LiteParse also needs LibreOffice for DOCX/PPTX/XLSX/CSV (use Docling without it). "
    "Prefer `.docx`, `.pptx`, and `.xlsx` when possible. "
    "JSON input is best as Docling Document JSON; other JSON is converted as plain text."
)

st.header("How to use")
st.markdown(
    """
**Single file**
1. Open **Single Document Parsing** in the sidebar.
2. In **Settings**, choose a **Parsing method** (Docling, PDFplumber, LiteParse, PyMuPDF, or Hybrid).
3. Upload one supported file (format limits depend on the method).
4. Optionally enable **OCR** (Docling / LiteParse / Hybrid), choose **Markdown** or **JSON**, then click **Convert**.
5. Preview and download the result (use **Show / Hide result** as needed).

**Bulk folder**
1. Open **Bulk Parsing** in the sidebar.
2. Upload multiple files (select all files from a folder if needed); set a **Default method for Document** (or **Auto Selection**) if you like.
3. In the file table, choose **Method** per file (Docling / PDFplumber / LiteParse / PyMuPDF / Hybrid where supported).
4. Click **Start convert** and watch the live dashboard (Done / In progress / Pending / Failed).
5. Preview one converted file at a time, uncheck any files to exclude from the ZIP, then download.

**Tips**
- First conversion may take longer while Docling downloads models; later runs are faster.
- Large PDFs and high-resolution images need more time and memory.
- For RAG, Markdown is usually a good starting export; JSON keeps richer structure.
"""
)

st.header("Reference")
st.markdown(
    "Please cite Docling if you use this tool in research or publications:"
)
st.code(
    r"""@techreport{Docling,
  author = {Deep Search Team},
  month = {8},
  title = {Docling Technical Report},
  url = {https://arxiv.org/abs/2408.09869},
  eprint = {2408.09869},
  doi = {10.48550/arXiv.2408.09869},
  version = {1.0.0},
  year = {2024}
}""",
    language="bibtex",
)
st.markdown(
    "Docling: [arXiv:2408.09869](https://arxiv.org/abs/2408.09869) · "
    "[GitHub](https://github.com/docling-project/docling)  \n"
    "PDFplumber: [jsvine/pdfplumber](https://github.com/jsvine/pdfplumber)  \n"
    "LiteParse: [run-llama/liteparse](https://github.com/run-llama/liteparse)  \n"
    "PyMuPDF: [pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF)"
)

st.markdown("---")
c1, c2 = st.columns(2)
with c1:
    st.page_link(
        "pages/1_Single_Document_Parsing.py",
        label="Single Document Parsing →",
        icon="📄",
    )
with c2:
    st.page_link("pages/2_Bulk_Parsing.py", label="Bulk Parsing →", icon="📁")
