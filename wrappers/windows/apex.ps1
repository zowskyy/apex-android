#Requires -Version 5.1
param(
    [Parameter(Position = 0)]
    [string] $Mode = "gui",
    [int] $Port = 8765
)

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Venv = Join-Path $Root ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path $Py)) {
    Write-Host "Creating Python virtual environment..."
    try { py -3 -m venv $Venv } catch { python -m venv $Venv }
    & (Join-Path $Venv "Scripts\pip.exe") install -q --upgrade pip wheel
    & (Join-Path $Venv "Scripts\pip.exe") install -q -e $Root
}

$env:APEX_WRAPPER_ROOT = $Root
$argsList = @($Mode)
if ($Mode -eq "mobile") { $argsList += @("--port", $Port) }
& $Py -m apex @argsList
