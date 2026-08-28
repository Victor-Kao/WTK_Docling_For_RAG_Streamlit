# Documents Parsing Tool

Streamlit app that converts documents to **Markdown** or **JSON** for RAG and other pipelines.

**Parsers**
- [Docling](https://github.com/docling-project/docling)
- [PDFplumber](https://github.com/jsvine/pdfplumber)
- [LiteParse](https://github.com/run-llama/liteparse)
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF)
- **Hybrid** (PDF only) — fast parser by default; **Docling** only on pages that contain tables
- **LLM API** — cloud Gemini or OpenAI-compatible gateway (no local models / no Hugging Face)

Supports **single-file** parsing and **bulk** multi-file parsing with live status, result preview, and selective ZIP download.

---

## What to install first (before downloading / running)

| Need | Required? | Why |
|------|-----------|-----|
| **Python 3.10–3.13** | Yes | Runs the app (`python`, `pip`) |
| **Git** | Recommended | Clone this repository |
| **Internet** | Yes (first run) | `pip install` + Docling/LiteParse may download models |
| **LibreOffice** | Optional | Only if you want **LiteParse** on DOCX / PPTX / XLSX / CSV |
| **Disk / RAM** | Recommended | Docling + models can use several GB |

> Tip on Windows: prefer **Python 3.11/3.12** or **Anaconda**. Avoid odd standalone installs that conflict on `PATH` (e.g. a separate Python 3.14 with its own Streamlit).

---

## Quick start (Windows — easiest)

1. Install [Python 3.12](https://www.python.org/downloads/) (check **Add Python to PATH**), **or** use company **Anaconda**.
2. Download or clone this repo, then open the project folder.
3. Double-click **`setup.bat`** (creates `.venv` if allowed; otherwise installs with `pip --user`).  
   First install can take several minutes.
4. Double-click **`run.bat`** to start the app.
5. Open the URL shown in the terminal (usually `http://localhost:8501`).

### Company PC — cannot create `.venv`

Many corporate machines block `python -m venv`. You do **not** need a venv.

**Option A — batch file**

1. Double-click **`setup_no_venv.bat`** (installs into your user Python via `pip --user`)
2. Double-click **`run.bat`**

**Option B — Anaconda Prompt** (often already approved by IT)

```powershell
cd path\to\WTK_Docling_For_RAG_Streamlit
python -m pip install --user -r requirements.txt
python -m streamlit run Home.py
```

**Option C — manual (no venv)**

```bat
python -m pip install --user -r requirements.txt
python -m streamlit run Home.py
```

If `pip` itself is blocked, ask IT for a Python/Anaconda environment where you can install packages, or request `streamlit`, `docling`, `pdfplumber`, `liteparse`, and `pymupdf`.

Optional (LiteParse for Office/CSV):

```powershell
winget install --id TheDocumentFoundation.LibreOffice -e
```

Then restart the terminal / app so `soffice` is on `PATH`.

---

## Clone and setup (any OS)

```bash
git clone https://github.com/Victor-Kao/WTK_Docling_For_RAG_Streamlit.git
cd WTK_Docling_For_RAG_Streamlit
```

### Windows (manual)

With venv (if allowed):

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run Home.py
```

Without venv (company PC):

```bat
python -m pip install --user -r requirements.txt
python -m streamlit run Home.py
```

Or use the batch files:

```bat
setup.bat
rem if venv fails, use:
setup_no_venv.bat
run.bat
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run Home.py
```

### Anaconda (Windows)

```powershell
cd path\to\WTK_Docling_For_RAG_Streamlit
conda activate base
python -m pip install -r requirements.txt
python -m streamlit run Home.py
```

Use `python -m streamlit` so you do not launch the wrong Python/Streamlit from `PATH`.

---

## Features

- **Home** — overview, how-to, citations
- **Single Document Parsing** — one file, choose parser, preview, download
- **Bulk Parsing** — many files, per-file method, live dashboard, ZIP selection
- Output: **Markdown** or **JSON**
- OCR for Docling / LiteParse / Hybrid (Docling table pages)
- **Auto Selection** (bulk): PDFs → Hybrid; other files → LiteParse if possible, else Docling

## Supported inputs

| Method | Formats |
|--------|---------|
| **Docling** | PDF, PPT/PPTX, DOC/DOCX, XLS/XLSX, CSV, TXT, JSON, MD, HTML, images |
| **PDFplumber** | PDF only |
| **LiteParse** | PDF and images natively; DOCX/PPTX/XLSX/CSV only with LibreOffice |
| **PyMuPDF** | PDF, common images |
| **Hybrid** | PDF only — LiteParse/PyMuPDF by default; Docling on pages with tables |
| **LLM API** | All supported types via cloud API (Gemini upload or text/vision) |

Legacy Office (`.doc`, `.ppt`, `.xls`) and LiteParse Office conversion need LibreOffice. Without it, use **Docling** or **LLM API (Gemini)** for Office/CSV.

## LLM API (company gateway / no Hugging Face)

Use this when your PC **cannot download Hugging Face models** and you must use a **company-approved API** only.

1. In the sidebar, choose parsing method **LLM API**.
2. Pick **Gemini** (Google AI / company Gemini endpoint) or **OpenAI-compatible** (many internal gateways).
3. Paste your **API key** (stored in the browser session only — not saved to git).
4. Set **model** (e.g. `gemini-2.0-flash`, `gpt-4o`).
5. For OpenAI-compatible, set **API base URL** (e.g. `https://gateway.company.com/v1`).

| Provider | PDF / images | Office files | Notes |
|----------|--------------|--------------|-------|
| **Gemini** | Upload file to API | Upload when supported | No local models |
| **OpenAI-compatible** | Text extract via PyMuPDF, or vision for images | Text extract only | Needs base URL |

No Hugging Face, no `huggingface-cli`, no local LLM weights — only HTTP calls (`google-genai` or `requests`).

## Hybrid (PDF)

1. Detect pages that look like they contain tables (pdfplumber).
2. **No tables** → LiteParse (PDF ≤ 5 MB) or PyMuPDF (PDF > 5 MB).
3. **Has tables** → Docling on those pages only; other pages use PyMuPDF.
4. Merge into one Markdown/JSON result.

## Project structure

```text
.
├── Home.py                          # Intro / how-to / references
├── docling_utils.py                 # Shared parsers (all methods)
├── llm_api_utils.py                 # Cloud LLM API parsing (Gemini / OpenAI-compatible)
├── pages/
│   ├── 1_Single_Document_Parsing.py
│   └── 2_Bulk_Parsing.py
├── .streamlit/config.toml           # Streamlit settings (file watcher off)
├── requirements.txt
├── fix_opencv_headless.py           # Swap to opencv-python-headless (libGL fix)
├── fix_opencv_headless.sh           # Linux helper for the same fix
├── setup.bat                        # Windows: try .venv, else pip --user
├── setup_no_venv.bat                # Windows: company PC (no venv)
├── run.bat                          # Windows: start Streamlit
├── README.md
└── .gitignore
```

## Linux / Docker — `libGL.so.1` (Docling)

Docling pulls **OpenCV**. The GUI package (`opencv-python`) needs `libGL.so.1`, which many servers/containers do not have. Error looks like:

`ImportError: libGL.so.1: cannot open shared object file: No such file or directory`

**Preferred fix (no root):**

```bash
python -m pip uninstall -y opencv-python opencv-contrib-python
python fix_opencv_headless.py
# or:
bash fix_opencv_headless.sh
```

**Alternative (system packages):**

```bash
sudo apt-get update
sudo apt-get install -y libgl1 libglib2.0-0
```

Windows setup scripts run this OpenCV headless swap automatically after `pip install`.

## Notes

- `.streamlit/config.toml` sets `fileWatcherType = "none"` to avoid noisy `torch.classes` watcher errors (restart the app after code changes).
- First Docling / LiteParse run may download models and take longer.
- In bulk mode: set **Default method for Document**, override per row, use **Finish selection** before ZIP download.
- **Clear cache** on Bulk Parsing clears parser caches, results, and the uploader.

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| `streamlit` / wrong Python | Use `python -m streamlit run Home.py` or `run.bat` |
| Cannot create `.venv` | Use `setup_no_venv.bat` or `pip install --user -r requirements.txt` |
| `libGL.so.1` / Docling on Linux | Run `python fix_opencv_headless.py` or install `libgl1` (see section above) |
| LLM API empty / auth error | Check API key, model name, and base URL; confirm outbound HTTPS is allowed |
| LiteParse fails on PPTX/XLSX/CSV | Install LibreOffice, or use Docling / LLM API (Gemini) |
| Slow first run | Normal — models downloading |
| Out of memory on large PDFs | Use PyMuPDF / Hybrid, or split the file |
| `pip` / install blocked by IT | Ask for Anaconda or package allow-list (see requirements.txt) |

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
- PyMuPDF: https://github.com/pymupdf/PyMuPDF

## License

Add your preferred license for this project. Upstream libraries keep their own licenses
(Docling, PDFplumber, LiteParse, PyMuPDF).
