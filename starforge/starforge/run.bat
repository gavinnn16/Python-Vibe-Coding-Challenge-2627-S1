@echo off
cd /d "%~dp0"
title STARFORGE launcher

rem --- find Python ---
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto nopython

rem --- first run: create a private environment and install the libraries ---
if not exist ".venv\Scripts\python.exe" (
    echo First-time setup, this takes about a minute...
    %PY% -m venv .venv
    if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto fail

echo Starting STARFORGE...
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto fail
exit /b 0

:nopython
echo.
echo Python was not found. Install Python 3.12 from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" in the installer, then run this file again.
pause
exit /b 1

:fail
echo.
echo Something went wrong. Take a screenshot of the text above and send it to the project author.
pause
exit /b 1
