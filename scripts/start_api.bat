@echo off
chcp 65001 >nul
title AI-Lab API Server
cd /d "%~dp0.."

REM Python 3.11+
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.11+ is required.
    pause
    exit /b 1
)

for /f "delims=" %%V in ('python -c "import core; print(core.__version__)"') do set "AI_LAB_VERSION=%%V"
echo ========================================
echo   AI-Lab API Server v%AI_LAB_VERSION%
echo ========================================
echo.

REM ?? .env ?????
python -c "from dotenv import load_dotenv; load_dotenv(); from core.provider_mode import get_provider_info; info=get_provider_info(); print(info['mode'])" > "%TEMP%\ai_lab_api_mode.txt" 2>nul
set /p AI_MODE=<"%TEMP%\ai_lab_api_mode.txt" 2>nul
del "%TEMP%\ai_lab_api_mode.txt" 2>nul

echo ?????%AI_MODE%
echo.

echo API?http://127.0.0.1:8000
echo OpenAPI?http://127.0.0.1:8000/docs
echo ========================================
echo.

python -m uvicorn api.app:app --host 127.0.0.1 --port 8000

echo.
echo API Server ????
pause
