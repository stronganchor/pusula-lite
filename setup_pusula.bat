@echo off
REM ---------------------------------------------------------------
REM  Pusula Lite — first-time setup script  (Windows 10/11, 64-bit)
REM ---------------------------------------------------------------

setlocal
set PY_VER=3.12.3
set PY_EXE=python-%PY_VER%-amd64.exe
set PY_URL=https://www.python.org/ftp/python/%PY_VER%/%PY_EXE%

set GIT_VER=2.43.0
set GIT_EXE=Git-%GIT_VER%-64-bit.exe
set GIT_URL=https://github.com/git-for-windows/git/releases/download/v%GIT_VER%.windows.1/%GIT_EXE%

set REPO_URL=https://github.com/stronganchor/pusula-lite.git

echo.
echo === Step 1: Check Python presence ===
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python not found — downloading %PY_EXE%
    powershell -Command "Invoke-WebRequest '%PY_URL%' -OutFile '%PY_EXE%'"
    echo Installing Python %PY_VER% silently...
    start /wait "" "%PY_EXE%" ^
        /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del "%PY_EXE%"
) else (
    for /f "tokens=2 delims= " %%a in ('python --version') do set CUR_PY=%%a
    echo Python %CUR_PY% already installed.
)

echo.
echo === Step 2: Check Git presence ===
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo Git not found — downloading %GIT_EXE%
    powershell -Command "Invoke-WebRequest '%GIT_URL%' -OutFile '%GIT_EXE%'"
    echo Installing Git %GIT_VER% silently...
    start /wait "" "%GIT_EXE%" /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /COMPONENTS="icons,ext\reg\shellhere,assoc,assoc_sh"
    del "%GIT_EXE%"
    REM Add Git to PATH for this session
    set "PATH=%PATH%;C:\Program Files\Git\cmd"
) else (
    for /f "tokens=3 delims= " %%a in ('git --version') do set CUR_GIT=%%a
    echo Git %CUR_GIT% already installed.
)

echo.
echo === Step 3: Initialize Git repository ===
if not exist ".git" (
    echo Initializing Git repository...
    git init
    git remote add origin %REPO_URL%
    echo Fetching latest code from GitHub...
    git fetch origin
    git checkout -b main origin/main
    echo Repository initialized and synced.
) else (
    echo Git repository already initialized.
)

echo.
echo === Step 4: Upgrade pip ===
python -m pip install --upgrade pip

echo.
echo === Step 5: Install required packages ===
python -m pip install --upgrade sqlalchemy dbfread

echo.
echo === Step 6: Create data folder (if missing) ===
if not exist "data" mkdir data

echo.
echo === Step 7: Create desktop shortcut ===
powershell -nop -c "$s=New-Object -ComObject WScript.Shell; $sc=$s.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Pusula Lite.lnk'); $sc.TargetPath='%SystemRoot%\System32\pythonw.exe'; $sc.Arguments='%cd%\main.py'; $sc.WorkingDirectory='%cd%'; $sc.IconLocation='C:\Windows\py.exe,0'; $sc.Save();"

echo.
echo === Kurulum tamam!  Çalıştırmak için:  %cd%\main.py  ===
echo.
echo NOT: Güncellemeler için update_pusula.bat dosyasını çalıştırın.
pause
endlocal
