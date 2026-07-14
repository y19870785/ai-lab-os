@echo off
chcp 65001 >nul
title AI-Lab CEO Assistant
cd /d "%~dp0.."

REM ---- Python 3.11+ ----
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.11+ is required.
    pause
    exit /b 1
)

for /f "delims=" %%V in ('python -c "import core; print(core.__version__)"') do set "AI_LAB_VERSION=%%V"
echo ========================================
echo   AI-Lab CEO Assistant v%AI_LAB_VERSION%
echo ========================================
echo.

REM ---- ????????? SOCKS/httpx ???? ----
set HTTP_PROXY=
set HTTPS_PROXY=
set ALL_PROXY=
set http_proxy=
set https_proxy=
set all_proxy=

REM ---- ?? .env ??? provider ?? ----
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
    ) else (
        echo OPENAI_API_KEY= > .env
    )
)

python -c "from dotenv import load_dotenv; load_dotenv(); from core.provider_mode import detect_provider_mode, get_provider_info; info = get_provider_info(); print(info['mode'])" > "%TEMP%\ai_lab_mode.txt" 2>nul
set /p AI_MODE=<"%TEMP%\ai_lab_mode.txt" 2>nul
del "%TEMP%\ai_lab_mode.txt" 2>nul

if "%AI_MODE%"=="real" (
    echo ?????REAL
    for /f "tokens=*" %%i in ('python -c "from dotenv import load_dotenv; load_dotenv(); from core.provider_mode import get_provider_info; info=get_provider_info(); print(info['provider']); print(info['base_url']); print(info['model']); print(info['api_key_masked'])"') do echo   %%i
) else if "%AI_MODE%"=="invalid" (
    echo [ERROR] Provider ???????????
    echo ???????? .env ???
    pause
    exit /b 1
) else (
    echo ?????MOCK
    echo ?????????? API Key????????????
)

echo.
echo ?? CEO Assistant...
echo ?? /help ?????/exit ???
echo ========================================
echo.

python -m cli ceo

echo.
echo CEO Assistant ????
exit /b 0
