"""Copy RapidOCR PP-OCRv6 ONNX weights into ./model/ for offline Docling OCR."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_DIR = PROJECT_ROOT / "model"

# Keep in sync with docling_utils.LOCAL_OCR_FILES
FILES = (
    "PP-OCRv6_det_small.onnx",
    "PP-OCRv6_rec_small.onnx",
    "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
    "ppocrv6_dict.txt",
)


def rapidocr_models_dir() -> Path:
    try:
        import rapidocr
    except ImportError as exc:
        raise SystemExit(
            "rapidocr is not installed. Run: pip install rapidocr onnxruntime"
        ) from exc
    return Path(rapidocr.__file__).resolve().parent / "models"


def main() -> int:
    src_dir = rapidocr_models_dir()
    if not src_dir.is_dir():
        print(f"RapidOCR models folder not found: {src_dir}", file=sys.stderr)
        return 1

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for name in FILES:
        src = src_dir / name
        dest = MODEL_DIR / name
        if not src.is_file():
            print(f"Missing source file: {src}", file=sys.stderr)
            return 1
        shutil.copy2(src, dest)
        print(f"Copied {name} -> {dest}")
        copied += 1

    print(f"Done. {copied} file(s) in {MODEL_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
