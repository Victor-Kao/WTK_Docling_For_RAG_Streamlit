@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo  Documents Parsing Tool - Setup (NO venv)
echo ============================================
echo.
echo Use this on company PCs where creating .venv is blocked.
echo Installs packages into the current Python with: pip --user
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found on PATH.
  echo Options:
  echo   - Install Python and enable "Add to PATH"
  echo   - Or open Anaconda Prompt and run this script there
  pause
  exit /b 1
)

echo Using:
python --version
python -c "import sys; print(sys.executable)"
echo.

echo Upgrading pip (user)...
python -m pip install --upgrade pip --user
if errorlevel 1 (
  echo [ERROR] pip upgrade failed
  pause
  exit /b 1
)

echo.
echo Installing requirements with --user ...
python -m pip install --user -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERROR] Install failed.
  echo Ask IT if pip / user site-packages is blocked,
  echo or use a managed Anaconda/miniconda environment they provide.
  pause
  exit /b 1
)

echo.
echo Fixing OpenCV for headless / Linux Docling (libGL.so.1)...
python fix_opencv_headless.py
if errorlevel 1 (
  echo [WARN] OpenCV headless fix reported a problem.
  echo On Linux you may need: sudo apt-get install -y libgl1 libglib2.0-0
)

echo.
echo ============================================
echo  Setup finished (no venv).
echo  Next: double-click run.bat
echo ============================================
pause
endlocal
