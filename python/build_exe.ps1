$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv310\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = Join-Path $PSScriptRoot ".venv312\Scripts\python.exe"
}
if (-not (Test-Path $python)) {
    $python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
}
if (-not (Test-Path $python)) {
    throw "Python executable was not found. Create python\.venv312 or workspace\.venv first."
}

& $python -m pip install -r requirements.txt
& $python -m PyInstaller --noconfirm --clean --onefile --name Vymora `
    --add-data "templates;templates" `
    --collect-data demucs `
    --hidden-import demucs.separate `
    --hidden-import demucs.apply `
    --hidden-import demucs.audio `
    --hidden-import demucs.pretrained `
    --hidden-import demucs.htdemucs `
    --exclude-module sklearn `
    --exclude-module dask `
    app.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host "Built dist\Vymora.exe"