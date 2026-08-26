@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo  Documents Parsing Tool - Start
echo ============================================
echo.

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
  echo Using venv: .venv
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] No .venv and no Python on PATH.
    echo Run setup.bat or setup_no_venv.bat first.
    pause
    exit /b 1
  )
  set "PY=python"
  echo Using system / Anaconda Python (no .venv).
  echo If imports fail, run setup_no_venv.bat once.
)

echo.
echo Starting Streamlit...
echo When ready, open the URL shown below (usually http://localhost:8501)
echo Press Ctrl+C in this window to stop the app.
echo.

"%PY%" -m streamlit run Home.py
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo.
  echo [ERROR] Streamlit exited with code %EXITCODE%.
  echo If packages are missing, run setup.bat or setup_no_venv.bat.
  pause
)
endlocal
exit /b %EXITCODE%
