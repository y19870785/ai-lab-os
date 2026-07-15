@echo off
chcp 65001 >nul
setlocal
title AI-Lab API Server
set "PYTHON_CMD=python"
if defined AI_LAB_PYTHON set "PYTHON_CMD=%AI_LAB_PYTHON%"
if defined AI_LAB_RUNTIME_ROOT (
    cd /d "%AI_LAB_RUNTIME_ROOT%"
) else (
    cd /d "%~dp0.."
)
if errorlevel 1 (
    echo [ERROR] Cannot enter the runtime directory.
    exit /b 1
)

REM Python 3.11+
call "%PYTHON_CMD%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11+ is required.
    if not defined AI_LAB_NONINTERACTIVE pause
    exit /b 1
)

set "VERSION_FILE=%TEMP%\ai_lab_api_version_%RANDOM%.txt"
call "%PYTHON_CMD%" -c "import core; print(core.__version__)" > "%VERSION_FILE%" 2>nul
if errorlevel 1 (
    del "%VERSION_FILE%" 2>nul
    echo [ERROR] AI-Lab version resolution failed.
    exit /b 1
)
set /p AI_LAB_VERSION=<"%VERSION_FILE%"
del "%VERSION_FILE%" 2>nul
if not defined AI_LAB_VERSION (
    echo [ERROR] AI-Lab version is empty.
    exit /b 1
)
echo ========================================
echo   AI-Lab API Server v%AI_LAB_VERSION%
echo ========================================
echo.

REM Load provider mode from .env
set "MODE_FILE=%TEMP%\ai_lab_api_mode_%RANDOM%.txt"
call "%PYTHON_CMD%" -c "from dotenv import load_dotenv; load_dotenv(); from core.provider_mode import get_provider_info; print(get_provider_info()['mode'])" > "%MODE_FILE%" 2>nul
if errorlevel 1 (
    del "%MODE_FILE%" 2>nul
    echo [ERROR] Provider mode detection failed.
    exit /b 1
)
set /p AI_MODE=<"%MODE_FILE%"
del "%MODE_FILE%" 2>nul
if not defined AI_MODE (
    echo [ERROR] Provider mode is empty.
    exit /b 1
)

echo Provider mode: %AI_MODE%
echo.

echo API: http://127.0.0.1:8000
echo OpenAPI: http://127.0.0.1:8000/docs
echo ========================================
echo.

call "%PYTHON_CMD%" -m uvicorn api.app:app --host 127.0.0.1 --port 8000
set "API_EXIT=%errorlevel%"
if not "%API_EXIT%"=="0" (
    echo.
    echo [ERROR] API Server exited with code %API_EXIT%.
    exit /b %API_EXIT%
)

echo.
echo API Server closed.
exit /b 0
