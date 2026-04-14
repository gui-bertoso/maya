

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".venv")) {
    py -3.11 -m venv .venv
}

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

& $python -m pip install --upgrade pip
& $python -m pip install pyinstaller
& $python -m PyInstaller --noconfirm --clean setup.spec

Write-Host ""
Write-Host "Build finalizado."
Write-Host "Executavel: dist\setup.exe"
