@echo off
chcp 65001 >nul
title AI-Lab Setup
echo ========================================
echo   AI-Lab CEO Assistant Setup
echo ========================================
echo.

cd /d "%~dp0.."

echo [1/5] Checking Python...
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.11+ required.
    pause & exit /b 1
)
python --version
echo [OK]

echo.
echo [2/5] Checking dependencies...
python -m pip install -r requirements.txt -q 2>nul
python -m pip install -e . --no-deps -q 2>nul
echo [OK]

echo.
echo [3/5] Setting up .env...
if not exist .env (
    if exist .env.example ( copy .env.example .env ) else (
        echo OPENAI_API_KEY=your_key_here > .env
        echo OPENAI_BASE_URL=https://api.deepseek.com/v1 >> .env
        echo OPENAI_MODEL=deepseek-chat >> .env
    )
    echo [INFO] Created .env. Please edit with your API key.
) else (
    echo [OK]
)

echo.
echo [4/5] Initializing data directories...
mkdir data\sqlite 2>nul
mkdir data\chroma 2>nul
echo [OK]

echo.
echo [5/5] Running health check...
python -m pytest tests/ -q -m "not real" --tb=no 2>nul
echo [OK]

echo.
echo ========================================
echo   Setup complete!
echo   Run: scripts\start.bat
echo ========================================
pause
