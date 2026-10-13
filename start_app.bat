@echo off
title OS RPA Tool Studio
cd /d "%~dp0"

echo ====================================================
echo             Starting OS RPA Tool Studio
echo ====================================================
echo.

:: Trust the Windows certificate store in Node/npm (corporate TLS inspection, e.g. Zscaler)
set NODE_USE_SYSTEM_CA=1
if exist "%USERPROFILE%\.certs\corp-ca.pem" set "NODE_EXTRA_CA_CERTS=%USERPROFILE%\.certs\corp-ca.pem"

:: Check if virtual environment exists; if not, create it and install requirements
if not exist ".venv\Scripts\python.exe" (
    echo [*] Virtual environment not found. Setting up .venv ...
    where python >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Python was not found in your PATH!
        echo Please install Python 3.10 or higher and ensure it is added to your PATH.
        pause
        exit /b 1
    )

    echo [*] Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )

    echo [*] Upgrading pip...
    .\.venv\Scripts\python.exe -m pip install --upgrade pip

    if exist "requirements.txt" (
        echo [*] Installing requirements from requirements.txt ...
        .\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
        if errorlevel 1 (
            echo [ERROR] Failed to install dependencies from requirements.txt!
            echo App execution aborted.
            pause
            exit /b 1
        )
    )
    echo [SUCCESS] Environment setup and package installation complete!
    echo.
)

:: Build the Studio UI if it has not been built yet
if not exist "studio\dist\index.html" (
    echo [*] Studio UI not built. Building studio\dist ...
    where npm >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Node.js/npm was not found in your PATH!
        echo Please install Node.js 22 or higher to build the Studio UI.
        pause
        exit /b 1
    )
    pushd studio
    call npm ci
    if errorlevel 1 (
        popd
        echo [ERROR] npm ci failed! If you are behind a proxy, check its certificate setup.
        pause
        exit /b 1
    )
    call npm run build
    if errorlevel 1 (
        popd
        echo [ERROR] Studio UI build failed!
        pause
        exit /b 1
    )
    popd
    echo [SUCCESS] Studio UI built.
    echo.
)

echo [*] Launching OS RPA Studio Server at http://localhost:8000 ...
echo [*] Opening browser in 2 seconds...

:: Open browser automatically after server starts
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

:: Start the Python server hosting both the Studio UI and Engine API
.\.venv\Scripts\python.exe -m os_rpa.cli server --port 8000

pause

