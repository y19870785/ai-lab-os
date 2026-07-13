@echo off
chcp 65001 >nul
title AI-Lab Diagnosis
echo ========================================
echo   AI-Lab System Diagnosis
echo ========================================
echo.

cd /d "%~dp0.."

echo [1] Python version:
python --version 2>nul || echo   NOT FOUND

echo.
echo [2] Environment:
if exist .env (echo   .env: EXISTS) else (echo   .env: MISSING)
for /f "tokens=2 delims==" %%a in ('findstr "OPENAI_API_KEY" .env 2^>nul') do set KEY=%%a
if defined KEY (echo   API Key: CONFIGURED) else (echo   API Key: NOT SET)

echo.
echo [3] Dependencies:
python -c "import openai; print('  openai: OK')" 2>nul || echo "  openai: MISSING"
python -c "import chromadb; print('  chromadb: OK')" 2>nul || echo "  chromadb: MISSING"
python -c "import sentence_transformers; print('  sentence_transformers: OK')" 2>nul || echo "  sentence_transformers: MISSING"

echo.
echo [4] Test statistics:
python -m pytest tests/ -q -m "not real" --tb=no 2>nul

echo.
echo ========================================
pause