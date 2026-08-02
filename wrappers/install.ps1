#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

Write-Host "==> Installing APEX Python package"
$Venv = Join-Path $Root ".venv"
if (-not (Test-Path $Venv)) { py -3 -m venv $Venv 2>$null; if (-not (Test-Path $Venv)) { python -m venv $Venv } }
& (Join-Path $Venv "Scripts\pip.exe") install -q --upgrade pip wheel
& (Join-Path $Venv "Scripts\pip.exe") install -q -e ".[mcp]"

try {
    & (Join-Path $Venv "Scripts\pip.exe") install -q maturin
    & (Join-Path $Venv "Scripts\maturin.exe") develop --release -m core/zip_reader/Cargo.toml
    & (Join-Path $Venv "Scripts\maturin.exe") develop --release -m core/dex_reader/Cargo.toml
} catch {
    Write-Warning "Native extensions build skipped (install Rust + maturin for full speed)"
}

$Desktop = [Environment]::GetFolderPath("Desktop")
Copy-Item (Join-Path $Root "wrappers\windows\apex-gui.bat") (Join-Path $Desktop "APEX.bat") -Force
Copy-Item (Join-Path $Root "wrappers\windows\apex-mobile.bat") (Join-Path $Desktop "APEX Mobile.bat") -Force

Write-Host ""
Write-Host "Done. Desktop shortcuts:"
Write-Host "  APEX.bat"
Write-Host "  APEX Mobile.bat"
Write-Host "Or run: wrappers\windows\apex.ps1 mobile"
