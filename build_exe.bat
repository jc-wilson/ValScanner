@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist "%~dp0scripts\bootstrap.ps1" goto extracted
 echo Extract the entire downloaded ZIP first, then run build_exe.bat again.
if /I not "%~1"=="--no-pause" pause
exit /b 1
:extracted
set "BUILD_SHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%BUILD_SHELL%" (
    echo Windows PowerShell is required. This build supports Windows 10 and 11.
    pause
    exit /b 1
)
if /I "%~1"=="--no-pause" goto unattended
"%BUILD_SHELL%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1"
set "BUILD_RESULT=%ERRORLEVEL%"
pause
exit /b %BUILD_RESULT%
:unattended
"%BUILD_SHELL%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1" -NoReveal
exit /b %ERRORLEVEL%
