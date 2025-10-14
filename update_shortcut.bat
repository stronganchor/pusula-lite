@echo off
setlocal enabledelayedexpansion
echo Updating desktop shortcut to hide command window...

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
powershell -nop -c "$s=New-Object -ComObject WScript.Shell; $sc=$s.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Pusula Lite.lnk'); $sc.TargetPath='%PYTHONW_PATH%'; $sc.Arguments='\""%cd%\main.py\""; $sc.WorkingDirectory='%cd%'; $sc.IconLocation='C:\Windows\py.exe,0'; $sc.Save();"

echo.
echo Shortcut updated!
pause
endlocal
