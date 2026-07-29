$ErrorActionPreference = "Stop"

$Python = if ($env:AI_LAB_PYTHON) {
    $env:AI_LAB_PYTHON
} else {
    ".\.venv_312\Scripts\python.exe"
}

& $Python -m cli profile
if ($LASTEXITCODE -ne 0) {
    throw "Local Daily Profile validation failed."
}

& $Python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
