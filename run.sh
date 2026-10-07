#!/usr/bin/env bash
set -e
echo "============================================"
echo "  AUST - Smart Attendance System"
echo "============================================"
echo ""
echo "[1/3] Installing dependencies..."
python3 -m pip install -r requirements.txt --quiet
echo ""
echo "[2/3] Initializing database..."
python3 database/init_database.py
echo ""
echo "[3/3] Starting application..."
python3 main.py
