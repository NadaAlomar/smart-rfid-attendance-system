import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATABASE_PATH = BASE_DIR / "data" / "attendance.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

UPLOAD_FOLDER = BASE_DIR / "uploads"
BACKUP_FOLDER = BASE_DIR / "backups"

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

SESSION_TIMEOUT_MINUTES = 15

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000
API_BASE = f"http://127.0.0.1:{SERVER_PORT}"

MAX_CONTENT_LENGTH = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {"xlsx", "xls"}

RFID_MODE = "http"
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

SERIAL_PORT = None
SERIAL_BAUD_RATE = 9600
SERIAL_TIMEOUT = 1
DEFAULT_HALL_ID = 1

# Create required directories on import
os.makedirs(DATABASE_PATH.parent, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)
