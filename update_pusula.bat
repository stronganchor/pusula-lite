@echo off
echo Updating desktop shortcut to hide command window...

REM Find pythonw.exe using py launcher
py -c "import sys; print(sys.executable.replace('python.exe', 'pythonw.exe'))" > temp_path.txt 2>nul
set /p PYTHONW_PATH=<temp_path.txt
del temp_path.txt

if not defined PYTHONW_PATH (
    echo ERROR: Cannot find Python installation
    pause
    exit /b 1
)

if not exist "%PYTHONW_PATH%" (
    echo WARNING: pythonw.exe not found, using python.exe instead
    py -c "import sys; print(sys.executable)" > temp_path.txt 2>nul
    set /p PYTHONW_PATH=<temp_path.txt
    del temp_path.txt
)

echo Found: %PYTHONW_PATH%
echo.

powershell -nop -c "$s=New-Object -ComObject WScript.Shell; $sc=$s.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Pusula Lite.lnk'); $sc.TargetPath='%PYTHONW_PATH%'; $sc.Arguments='%cd%\main.py'; $sc.WorkingDirectory='%cd%'; $sc.IconLocation='C:\Windows\py.exe,0'; $sc.Save();"

echo.
echo Shortcut updated!
pause
