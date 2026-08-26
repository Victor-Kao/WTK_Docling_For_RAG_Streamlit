"""Force opencv-python-headless so Docling works without system libGL.so.1."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    py = sys.executable
    print("Removing opencv-python (GUI) if present...")
    subprocess.run(
        [py, "-m", "pip", "uninstall", "-y", "opencv-python", "opencv-contrib-python"],
        check=False,
    )
    print("Installing opencv-python-headless...")
    result = subprocess.run(
        [py, "-m", "pip", "install", "--no-cache-dir", "opencv-python-headless>=4.8.0"],
        check=False,
    )
    if result.returncode != 0:
        print("Failed to install opencv-python-headless", file=sys.stderr)
        return result.returncode
    try:
        import cv2  # noqa: F401

        print("OpenCV headless OK:", getattr(cv2, "__file__", "cv2"))
    except Exception as exc:  # pragma: no cover
        print("Warning: cv2 import still failed:", exc, file=sys.stderr)
        print(
            "On Linux you can also install: sudo apt-get install -y libgl1 libglib2.0-0",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
