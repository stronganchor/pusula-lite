@echo off
echo Updating desktop shortcut to hide command window...

REM Find python.exe location
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
    echo WARNING: pythonw.exe not found at %PYTHONW_PATH%
    echo Using python.exe instead ^(command window will be visible^)
    set PYTHONW_PATH=%PYTHON_PATH%
)

echo Found: %PYTHONW_PATH%
echo.

powershell -nop -c "$s=New-Object -ComObject WScript.Shell; $sc=$s.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Pusula Lite.lnk'); $sc.TargetPath='%PYTHONW_PATH%'; $sc.Arguments='%cd%\main.py'; $sc.WorkingDirectory='%cd%'; $sc.IconLocation='C:\Windows\py.exe,0'; $sc.Save();"

echo.
echo Shortcut updated! The application will no longer show a command window.
pause
