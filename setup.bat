@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo  Documents Parsing Tool - Setup
echo ============================================
echo.
echo Tries a local .venv first.
echo If venv is blocked (common on company PCs),
echo installs into the current Python with --user.
echo.
echo Optional later: LibreOffice for LiteParse on Office/CSV
echo   winget install --id TheDocumentFoundation.LibreOffice -e
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found on PATH.
  echo Install Python 3.10-3.13, or use Anaconda and open
  echo "Anaconda Prompt", then run this script again.
  pause
  exit /b 1
)

echo Using:
python --version
python -c "import sys; print(sys.executable)"
echo.

set "PY="
set "MODE="

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
  set "MODE=venv"
  echo Found existing .venv
  goto :install
)

echo Trying to create virtual environment .venv ...
python -m venv .venv
if errorlevel 1 (
  echo.
  echo [WARN] Could not create .venv (policy / permissions).
  echo Falling back to: current Python + pip --user
  echo.
  set "PY=python"
  set "MODE=user"
  goto :install
)

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo [WARN] .venv was not created. Falling back to pip --user.
  set "PY=python"
  set "MODE=user"
  goto :install
)

set "PY=.venv\Scripts\python.exe"
set "MODE=venv"
echo Created .venv

:install
echo.
echo Upgrading pip ...
if /i "%MODE%"=="user" (
  "%PY%" -m pip install --upgrade pip --user
) else (
  "%PY%" -m pip install --upgrade pip
)
if errorlevel 1 (
  echo [ERROR] pip upgrade failed
  pause
  exit /b 1
)

echo.
echo Installing requirements (this may take several minutes)...
if /i "%MODE%"=="user" (
  "%PY%" -m pip install --user -r requirements.txt
) else (
  "%PY%" -m pip install -r requirements.txt
)
if errorlevel 1 (
  echo.
  echo [ERROR] Dependency install failed.
  echo If you see "Permission denied", try:
  echo   setup_no_venv.bat
  echo or Anaconda Prompt:
  echo   python -m pip install --user -r requirements.txt
  pause
  exit /b 1
)

echo.
echo Fixing OpenCV for headless / Linux Docling (libGL.so.1)...
"%PY%" fix_opencv_headless.py
if errorlevel 1 (
  echo [WARN] OpenCV headless fix reported a problem.
  echo On Linux you may need: sudo apt-get install -y libgl1 libglib2.0-0
)

echo.
echo ============================================
echo  Setup finished. Mode: %MODE%
if /i "%MODE%"=="user" (
  echo  Packages installed for this user Python.
  echo  No .venv was required.
)
echo  Next: double-click run.bat
echo ============================================
pause
endlocal
