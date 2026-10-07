@echo off
cd /d "%~dp0"
echo ============================================
echo   AUST - Smart Attendance System
echo ============================================
echo.
echo [1/3] Installing dependencies...
python -m pip install -r requirements.txt --quiet
echo.
echo [2/3] Initializing database...
python database\init_database.py
echo.
echo [3/3] Starting application...
python main.py
echo.
pause
