# Documents Parsing Tool

Streamlit app for converting documents to Markdown or JSON using multiple parsers:

- [Docling](https://github.com/docling-project/docling)
- [PDFplumber](https://github.com/jsvine/pdfplumber)
- [LiteParse](https://github.com/run-llama/liteparse)

Supports single-file conversion and bulk folder parsing with a live status dashboard and selective ZIP download.

## Features

- **Home** — tool overview, usage guide, and citations
- **Single Document Parsing** — upload one file, choose a parser, preview, and download
- **Bulk Parsing** — upload a folder, set methods per file, track Done / In progress / Failed, preview results, then download a ZIP of selected outputs
- Output formats: **Markdown** or **JSON**
- Optional **OCR** for Docling and LiteParse

## Supported inputs

| Method | Formats |
|--------|---------|
| **Docling** | PDF, PPT/PPTX, DOC/DOCX, XLS/XLSX, CSV, TXT, JSON, MD, HTML, images |
| **PDFplumber** | PDF only |
| **LiteParse** | PDF, DOCX/XLSX/PPTX, images |

Legacy Office formats (`.doc`, `.ppt`, `.xls`) and some Office conversions may require LibreOffice.

## Requirements

- Python 3.10+
- Windows / macOS / Linux

## Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd WTK_Docling_For_RAG_Streamlit

# (Recommended) create a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Run

```bash
streamlit run Home.py
```

Then open the URL shown in the terminal (usually `http://localhost:8501`).

## Project structure

```text
.
├── Home.py                          # Introduction / how-to / references
├── docling_utils.py                 # Shared parsing helpers (Docling, PDFplumber, LiteParse)
├── pages/
│   ├── 1_Single_Document_Parsing.py # Single-file conversion
│   └── 2_Bulk_Parsing.py            # Folder bulk conversion + ZIP export
├── requirements.txt
├── README.md
└── .gitignore
```

## Usage tips

- The first Docling / LiteParse run may download models and take longer.
- In bulk mode, pick a method per file (e.g. PDFplumber for some PDFs, Docling or LiteParse for images).
- Use **Finish selection** before downloading the ZIP so only the files you keep are included.
- **Clear cache** on Bulk Parsing clears parser caches, conversion results, and the uploaded folder.

## References

```bibtex
@techreport{Docling,
  author = {Deep Search Team},
  month = {8},
  title = {Docling Technical Report},
  url = {https://arxiv.org/abs/2408.09869},
  eprint = {2408.09869},
  doi = {10.48550/arXiv.2408.09869},
  version = {1.0.0},
  year = {2024}
}
```

- Docling: https://arxiv.org/abs/2408.09869 · https://github.com/docling-project/docling
- PDFplumber: https://github.com/jsvine/pdfplumber
- LiteParse: https://github.com/run-llama/liteparse

## License

Add your preferred license for this project. Upstream libraries keep their own licenses (Docling, PDFplumber, LiteParse).
