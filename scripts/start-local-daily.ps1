param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot

$Python = if ($env:AI_LAB_PYTHON) {
    [System.IO.Path]::GetFullPath($env:AI_LAB_PYTHON, $ProjectRoot)
} else {
    Join-Path $ProjectRoot ".venv_312\Scripts\python.exe"
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Project Python 3.12 was not found: $Python"
}

& $Python -m cli profile --require-local-daily
if ($LASTEXITCODE -ne 0) {
    throw "Local Daily Profile validation failed."
}

& $Python -m uvicorn api.app:app --host 127.0.0.1 --port $Port
