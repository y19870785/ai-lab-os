@echo off
chcp 65001 >nul
setlocal
title AI-Lab CEO Assistant
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

REM ---- Python 3.11+ ----
call "%PYTHON_CMD%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11+ is required.
    if not defined AI_LAB_NONINTERACTIVE pause
    exit /b 1
)

set "VERSION_FILE=%TEMP%\ai_lab_version_%RANDOM%.txt"
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
echo   AI-Lab CEO Assistant v%AI_LAB_VERSION%
echo ========================================
echo.

REM ---- Avoid inherited proxy settings that conflict with local httpx ----
set HTTP_PROXY=
set HTTPS_PROXY=
set ALL_PROXY=
set http_proxy=
set https_proxy=
set all_proxy=

REM ---- Load provider mode from .env ----
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
    ) else (
        echo OPENAI_API_KEY= > .env
    )
)

set "MODE_FILE=%TEMP%\ai_lab_mode_%RANDOM%.txt"
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

if "%AI_MODE%"=="real" (
    echo Provider mode: REAL
    for /f "tokens=*" %%i in ('"%PYTHON_CMD%" -c "from dotenv import load_dotenv; load_dotenv(); from core.provider_mode import get_provider_info; info=get_provider_info(); print(info['provider']); print(info['base_url']); print(info['model']); print(info['api_key_masked'])"') do echo   %%i
) else if "%AI_MODE%"=="invalid" (
    echo [ERROR] Provider configuration is incomplete.
    echo Please check the project .env file.
    if not defined AI_LAB_NONINTERACTIVE pause
    exit /b 1
) else (
    echo Provider mode: MOCK
    echo No real API key is configured. Explicit Mock Provider will be used.
)

echo.
echo Starting CEO Assistant...
echo Enter /help for commands or /exit to quit.
echo ========================================
echo.

call "%PYTHON_CMD%" -m cli ceo
set "CLI_EXIT=%errorlevel%"
if not "%CLI_EXIT%"=="0" (
    echo.
    echo [ERROR] CEO Assistant exited with code %CLI_EXIT%.
    exit /b %CLI_EXIT%
)

echo.
echo CEO Assistant closed.
exit /b 0
