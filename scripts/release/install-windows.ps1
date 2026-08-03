# Offline install for APEX desktop release bundles (Windows).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Venv = Join-Path $Root ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"

Write-Host "==> Creating virtual environment"
if (-not (Test-Path $Venv)) {
  py -3 -m venv $Venv 2>$null
  if (-not (Test-Path $Venv)) { python -m venv $Venv }
}

& (Join-Path $Venv "Scripts\pip.exe") install -q --upgrade pip wheel
& (Join-Path $Venv "Scripts\pip.exe") install --no-index --find-links="$Root\wheels" "apex-android[mcp]"

$Desktop = [Environment]::GetFolderPath("Desktop")
Copy-Item (Join-Path $Root "wrappers\windows\apex-gui.bat") (Join-Path $Desktop "APEX.bat") -Force
Copy-Item (Join-Path $Root "wrappers\windows\apex-mobile.bat") (Join-Path $Desktop "APEX Mobile.bat") -Force

Write-Host ""
Write-Host "APEX installed."
Write-Host "  Desktop: APEX.bat, APEX Mobile.bat"
Write-Host "  $(Join-Path $Venv 'Scripts\apex.exe') doctor"
