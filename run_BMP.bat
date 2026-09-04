@echo off
setlocal

cd /d "%~dp0"

echo Starting BMP Player...
python BMP.py
if errorlevel 1 (
    echo.
    echo Failed to start BMP.py. Ensure Python is installed and on PATH.
    pause
    exit /b 1
)

endlocal
