#!/usr/bin/env bash
# Fix Docling ImportError: libGL.so.1 on Linux (prefer headless OpenCV).
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  PY=python
fi

echo "Using: $($PY -c 'import sys; print(sys.executable)')"
"$PY" fix_opencv_headless.py

echo
echo "If Docling still fails with libGL.so.1, install system libs:"
echo "  sudo apt-get update && sudo apt-get install -y libgl1 libglib2.0-0"
echo "  # Fedora: sudo dnf install mesa-libGL glib2"
