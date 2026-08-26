@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo  Documents Parsing Tool - Setup
echo ============================================
echo.
echo This will:
echo   1) Check Python
echo   2) Create .venv  (if missing)
echo   3) Install packages from requirements.txt
echo.
echo Optional later: LibreOffice for LiteParse on Office/CSV
echo   winget install --id TheDocumentFoundation.LibreOffice -e
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found on PATH.
  echo Install Python 3.10-3.13 from https://www.python.org/downloads/
  echo Enable "Add Python to PATH", then run this script again.
  pause
  exit /b 1
)

echo Using:
python --version
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment .venv ...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create .venv
    pause
    exit /b 1
  )
) else (
  echo Found existing .venv
)

echo.
echo Upgrading pip ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo [ERROR] pip upgrade failed
  pause
  exit /b 1
)

echo.
echo Installing requirements (this may take several minutes)...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Dependency install failed. Check the messages above.
  pause
  exit /b 1
)

echo.
echo ============================================
echo  Setup finished.
echo  Next: double-click run.bat
echo ============================================
pause
endlocal
