@echo off
title OS RPA Tool Studio
cd /d "%~dp0"

echo ====================================================
echo             Starting OS RPA Tool Studio
echo ====================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv!
    echo Please make sure the Python virtual environment is set up.
    pause
    exit /b 1
)

echo [*] Launching OS RPA Studio Server at http://localhost:8000 ...
echo [*] Opening browser in 3 seconds...

:: Open browser automatically after server starts
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

:: Start the Python server hosting both the Studio UI and Engine API
.\.venv\Scripts\python.exe -m os_rpa.cli server --port 8000

pause

