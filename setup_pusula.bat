@echo off
REM ---------------------------------------------------------------
REM  Pusula Lite – first-time setup script  (Windows 10/11, 64-bit)
REM ---------------------------------------------------------------

setlocal
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
for /f "delims=" %%i in ('where python 2^>nul') do set PYTHON_PATH=%%i
if not defined PYTHON_PATH (
    echo ERROR: Cannot find python.exe in PATH
    pause
    exit /b 1
)

REM Get the directory containing python.exe
for %%i in ("%PYTHON_PATH%") do set PYTHON_DIR=%%~dpi
set PYTHONW_PATH=%PYTHON_DIR%pythonw.exe

if not exist "%PYTHONW_PATH%" (
    echo ERROR: pythonw.exe not found at %PYTHONW_PATH%
    echo Using python.exe instead ^(command window will be visible^)
    set PYTHONW_PATH=%PYTHON_PATH%
)

echo Found: %PYTHONW_PATH%

echo.
echo === Step 6: Create desktop shortcut ===
powershell -nop -c "$s=New-Object -ComObject WScript.Shell; $sc=$s.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Pusula Lite.lnk'); $sc.TargetPath='%PYTHONW_PATH%'; $sc.Arguments='%cd%\main.py'; $sc.WorkingDirectory='%cd%'; $sc.IconLocation='C:\Windows\py.exe,0'; $sc.Save();"

echo.
echo === Kurulum tamam!  Çalıştırmak için:  %cd%\main.py  ===
pause
endlocal
