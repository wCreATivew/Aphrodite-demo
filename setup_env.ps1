param(
    [string]$VenvDir = ".venv"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $VenvDir)) {
    py -m venv $VenvDir
}

$pip = Join-Path $VenvDir "Scripts\pip.exe"
if (-not (Test-Path $pip)) {
    throw "pip not found in $VenvDir"
}

& $pip install --upgrade pip
& $pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}

Write-Host "Environment setup complete."
