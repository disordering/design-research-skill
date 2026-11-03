@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
 echo Node.js is required. Install Node.js LTS, then reopen this launcher.
 pause
 exit /b 1
)
node launch.mjs
pause
endlocal
