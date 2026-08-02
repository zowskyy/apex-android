@echo off
setlocal
cd /d "%~dp0\..\..\"
call wrappers\lib\common.bat gui %*
endlocal
