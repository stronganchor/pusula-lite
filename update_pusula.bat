@echo off
REM -------------------------------------------------------------
REM  update_pusula.bat  —  Pull latest code, refresh dependencies
REM -------------------------------------------------------------

cd /d "%~dp0"          REM go to script directory

echo === Fetching latest code from GitHub ===
git fetch origin
git reset --hard origin/main

if exist requirements.txt (
    echo.
    echo === Installing/Updating Python packages ===
    python -m pip install --upgrade -r requirements.txt
)

echo.
echo === Update complete!  Press any key to exit. ===
pause >nul
