@echo off
setlocal
set "campus_local_python=%~dp0..\..\..\work\d_execution_20261021\.venv\Scripts\python.exe"
if exist "%campus_local_python%" (
  "%campus_local_python%" "%~dp0serve.py" --port 4311
  exit /b
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0serve.py" --port 4311
  exit /b
)
python "%~dp0serve.py" --port 4311
