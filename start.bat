
@echo off
chcp 65001 >nul
title AUST Attendance System

echo.
echo  =====================================================
echo    AUST - University Smart Attendance System
echo  =====================================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Install Python 3.10+ from https://python.org
    echo  Check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo  [1/3] Installing requirements...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check

echo  [2/3] Initializing database...
python main.py init

echo  [3/3] Starting system...
echo.

REM -- Check firewall rule --
netsh advfirewall firewall show rule name="AUST Attendance Server" >nul 2>&1
if errorlevel 1 (
    echo  [WARN] Port 5000 is NOT open in firewall!
    echo  Arduino devices will NOT be able to connect.
    echo  Fix: Right-click firewall.bat ^> Run as Administrator
    echo.
)

python main.py

pause
