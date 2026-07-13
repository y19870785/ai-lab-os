@echo off
chcp 65001 >nul
title AI-Lab CEO Assistant
echo ========================================
echo   AI-Lab CEO Assistant v0.32.4
echo ========================================
echo.
cd /d "%~dp0.."

REM ---- ?? Python ----
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python ??????? Python 3.10+
    pause
    exit /b 1
)

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
