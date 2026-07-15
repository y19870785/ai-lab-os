@echo off
chcp 65001 >nul
setlocal
title AI-Lab Setup
echo ========================================
echo   AI-Lab CEO Assistant Setup
echo ========================================
echo.

set "PYTHON_CMD=python"
if defined AI_LAB_PYTHON set "PYTHON_CMD=%AI_LAB_PYTHON%"
if defined AI_LAB_SETUP_ROOT (
    cd /d "%AI_LAB_SETUP_ROOT%"
) else (
    cd /d "%~dp0.."
)
if errorlevel 1 (
    echo [ERROR] Cannot enter the setup directory.
    exit /b 1
)

echo [1/5] Checking Python...
call "%PYTHON_CMD%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11+ required.
    if not defined AI_LAB_SETUP_NONINTERACTIVE pause
    exit /b 1
)
call "%PYTHON_CMD%" --version
if errorlevel 1 (
    echo [ERROR] Python version check failed.
    exit /b 1
)
echo [OK]

echo.
echo [2/5] Checking dependencies...
call "%PYTHON_CMD%" -m pip install -e ".[local]"
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    if not defined AI_LAB_SETUP_NONINTERACTIVE pause
    exit /b 1
)
echo [OK]

echo.
echo [3/5] Setting up .env...
if not exist .env (
    if exist .env.example ( copy .env.example .env ) else (
        echo OPENAI_API_KEY=your_key_here > .env
        echo OPENAI_BASE_URL=https://api.deepseek.com/v1 >> .env
        echo OPENAI_MODEL=deepseek-v4-flash >> .env
    )
    if errorlevel 1 (
        echo [ERROR] Failed to create .env.
        exit /b 1
    )
    echo [INFO] Created .env. Please edit with your API key.
) else (
    echo [OK]
)

echo.
echo [4/5] Initializing data directories...
if not exist data\sqlite mkdir data\sqlite
if errorlevel 1 (
    echo [ERROR] Failed to create data\sqlite.
    exit /b 1
)
if not exist data\chroma mkdir data\chroma
if errorlevel 1 (
    echo [ERROR] Failed to create data\chroma.
    exit /b 1
)
echo [OK]

echo.
echo [5/5] Running health check...
call "%PYTHON_CMD%" -m pytest tests -q -m "not real" --tb=no
if errorlevel 1 (
    echo [ERROR] Test health check failed.
    if not defined AI_LAB_SETUP_NONINTERACTIVE pause
    exit /b 1
)
echo [OK]

echo.
echo ========================================
echo   Setup complete!
echo   Run: scripts\start.bat
echo ========================================
if not defined AI_LAB_SETUP_NONINTERACTIVE pause
exit /b 0
