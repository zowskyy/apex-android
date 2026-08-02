@echo off
setlocal EnableDelayedExpansion

set "ROOT=%~dp0\..\..\"
set "ROOT=%ROOT:~0,-1%"
set "VENV=%ROOT%\.venv"
set "PY=%VENV%\Scripts\python.exe"

if not exist "%PY%" (
  echo Creating Python virtual environment...
  py -3 -m venv "%VENV%" 2>nul || python -m venv "%VENV%"
  "%VENV%\Scripts\pip.exe" install -q --upgrade pip wheel
  "%VENV%\Scripts\pip.exe" install -q -e "%ROOT%"
)

set "APEX_WRAPPER_ROOT=%ROOT%"
"%PY%" -m apex %*
exit /b %ERRORLEVEL%
