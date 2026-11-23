@echo off
setlocal
cd /d "%~dp0"

rem Find a working Python command. Prefer the Windows Python Launcher.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 --version >nul 2>nul
    if not errorlevel 1 goto use_py
)

where python >nul 2>nul
if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 goto use_python
)

echo ERROR: Python 3 was not found.
echo Install Python from https://www.python.org/downloads/
echo During setup, enable the option to add Python to PATH.
echo.
pause
exit /b 1

:use_py
set "PYTHON_CMD=py -3"
goto run_app

:use_python
set "PYTHON_CMD=python"

:run_app
%PYTHON_CMD% -m pip --version >nul 2>nul
if errorlevel 1 (
    echo pip is missing. Trying to install pip...
    %PYTHON_CMD% -m ensurepip --upgrade
    if errorlevel 1 goto setup_error
)

echo Selected Python interpreter:
%PYTHON_CMD% -c "import sys; print(sys.executable)"
echo To list packages for this exact Python, use:
echo %PYTHON_CMD% -m pip list
echo.
echo Installing application requirements...
%PYTHON_CMD% -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto setup_error

echo Starting PyLibrary Manager...
%PYTHON_CMD% py_library_manager.py
if errorlevel 1 goto app_error
exit /b 0

:setup_error
echo.
echo ERROR: Could not install the required packages.
echo Check your internet connection and Python installation.
echo.
pause
exit /b 1

:app_error
echo.
echo ERROR: The application closed with an error.
echo.
pause
exit /b 1
