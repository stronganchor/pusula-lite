@echo off
setlocal enabledelayedexpansion
REM ---------------------------------------------------------------
REM  Pusula Lite – first-time setup script  (Windows 10/11, 64-bit)
REM ---------------------------------------------------------------

REM >>> CHANGE THIS IF YOU WANT A DIFFERENT PYTHON VERSION <
set PY_VER=3.12.3
set PY_EXE=python-%PY_VER%-amd64.exe
set PY_URL=https://www.python.org/ftp/python/%PY_VER%/%PY_EXE%

echo.
echo === Step 1: Check Python presence ===
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python not found – downloading %PY_EXE%
    powershell -Command "Invoke-WebRequest '%PY_URL%' -OutFile '%PY_EXE%'"
    echo Installing Python %PY_VER% silently...
    start /wait "" "%PY_EXE%" ^
        /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
) else (
    for /f "tokens=2 delims= " %%a in ('python --version') do set CUR_PY=%%a
    echo Python %CUR_PY% already installed.
)

echo.
echo === Step 2: Upgrade pip ===
python -m pip install --upgrade pip

echo.
echo === Step 3: Install required packages ===
python -m pip install --upgrade sqlalchemy dbfread

echo.
echo === Step 4: Create data folder (if missing) ===
if not exist "data" mkdir data

echo.
echo === Step 5: Locate pythonw.exe ===
set PYTHONW_PATH=

REM Try py.exe launcher first (most reliable)
for /f "delims=" %%i in ('py -c "import sys; print(sys.executable)" 2^>nul') do set PYTHON_PATH=%%i

if defined PYTHON_PATH (
    for %%i in ("!PYTHON_PATH!") do set PYTHON_DIR=%%~dpi
    set PYTHONW_PATH=!PYTHON_DIR!pythonw.exe

    if exist "!PYTHONW_PATH!" (
        echo Found pythonw: !PYTHONW_PATH!
    ) else (
        echo pythonw.exe not found, using python.exe
        set PYTHONW_PATH=!PYTHON_PATH!
    )
) else (
    REM Fallback: search PATH, excluding WindowsApps
    for /f "delims=" %%i in ('where python 2^>nul') do (
        set TEST_PATH=%%i
        echo !TEST_PATH! | findstr /i /v "WindowsApps" >nul
        if !errorlevel! equ 0 (
            set PYTHON_PATH=%%i
            goto :found_python
        )
    )
    :found_python

    if defined PYTHON_PATH (
        for %%i in ("!PYTHON_PATH!") do set PYTHON_DIR=%%~dpi
        set PYTHONW_PATH=!PYTHON_DIR!pythonw.exe
        if not exist "!PYTHONW_PATH!" set PYTHONW_PATH=!PYTHON_PATH!
        echo Found: !PYTHONW_PATH!
    ) else (
        echo ERROR: Cannot find Python installation
        pause
        exit /b 1
    )
)

echo.
echo === Step 6: Create desktop shortcut ===
powershell -nop -c "$s=New-Object -ComObject WScript.Shell; $sc=$s.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Pusula Lite.lnk'); $sc.TargetPath='%PYTHONW_PATH%'; $sc.Arguments='%cd%\main.py'; $sc.WorkingDirectory='%cd%'; $sc.IconLocation='C:\Windows\py.exe,0'; $sc.Save();"

echo.
echo === Kurulum tamam!  Çalıştırmak için:  %cd%\main.py  ===
pause
endlocal
