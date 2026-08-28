# Local RapidOCR models (Docling OCR)

Place ONNX weights here so Docling OCR can run **without downloading from Hugging Face**.

Required files (PP-OCRv6 small, onnxruntime):

| File | Role |
|------|------|
| `PP-OCRv6_det_small.onnx` | Text detection |
| `PP-OCRv6_rec_small.onnx` | Text recognition |
| `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | Line orientation |
| `ppocrv6_dict.txt` | Recognition charset |

## One-time copy from your Anaconda install

From the project root:

```powershell
D:\anaconda3\python.exe copy_local_ocr_models.py
```

This copies from `D:\anaconda3\Lib\site-packages\rapidocr\models\` into this folder.

Then in the app sidebar:

1. Check **Use local OCR models (model/ folder)**
2. Enable **Enable OCR**
3. Use parsing method **Docling** or **Hybrid** (Docling table pages)

`*.onnx` files are gitignored (large binaries). Copy them on each machine that needs offline OCR.
