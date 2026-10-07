@echo off
chcp 65001 >nul
title AUST Attendance System - Setup
color 0B

echo.
echo  ============================================
echo    AUST Attendance System - Setup
echo  ============================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Install Python 3.10+
    pause
    exit /b 1
)
echo  [OK] Python found
echo.

echo  [1/4] Installing requirements...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
echo  [OK] Done
echo.

echo  [2/4] Initializing database...
python main.py init
echo.

echo  [3/4] Setting up device token...
python setup_device.py
echo.

echo  [4/4] Opening firewall port 5000...
netsh advfirewall firewall show rule name="AUST Attendance Server" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="AUST Attendance Server" dir=in action=allow protocol=TCP localport=5000 >nul 2>&1
    if errorlevel 1 (
        echo  [WARN] Run this as Administrator to open firewall
    ) else (
        echo  [OK] Firewall rule added
    )
) else (
    echo  [OK] Firewall rule exists
)
echo.

echo  Your IP addresses:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do echo    %%a
echo.
echo  Put your WiFi IP in Arduino code:
echo    #define SERVER_IP  "YOUR_IP"
echo.
echo  ============================================
echo    Setup Complete! Run: start.bat
echo  ============================================
echo.
pause
