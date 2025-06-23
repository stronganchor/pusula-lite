@echo off
REM ---------------------------------------------------------------
REM  Pusula Lite – first-time setup script  (Windows 10/11, 64-bit)
REM ---------------------------------------------------------------

setlocal
REM >>> CHANGE THIS IF YOU WANT A DIFFERENT PYTHON VERSION <<<
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
echo === Step 5: Create desktop shortcut ===
powershell -nop -c ^
 "$s=New-Object -ComObject WScript.Shell;" ^
 "$sc=$s.CreateShortcut('$env:Public\Desktop\Pusula Lite.lnk');" ^
 "$sc.TargetPath='%cd%\main.py';" ^
 "$sc.Arguments='';" ^
 "$sc.IconLocation='%SystemRoot%\py.exe,0';" ^
 "$sc.Save();"

echo.
echo === Kurulum tamam!  Çalıştırmak için:  %cd%\main.py  ===
pause
endlocal
