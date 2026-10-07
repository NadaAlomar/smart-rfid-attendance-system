"""Migration 002: add scan_logs table + sim-time settings.

Idempotent: safe to run multiple times.
"""
import sqlite3
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "attendance.db")


CREATE_SCAN_LOGS = """
CREATE TABLE IF NOT EXISTS scan_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     DATETIME NOT NULL,
    hashed_uid    VARCHAR(255),
    raw_uid_hint  VARCHAR(50),
    device_id     VARCHAR(100),
    hall_id       INTEGER REFERENCES halls(id),
    scan_type     VARCHAR(20) NOT NULL,
    success       BOOLEAN NOT NULL DEFAULT 0,
    student_id    INTEGER REFERENCES students(id),
    doctor_id     INTEGER REFERENCES doctors(id),
    session_id    INTEGER REFERENCES attendance_sessions(id),
    error_reason  VARCHAR(200)
)
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_scan_logs_timestamp ON scan_logs(timestamp)",
    "CREATE INDEX IF NOT EXISTS ix_scan_logs_hall_id ON scan_logs(hall_id)",
    "CREATE INDEX IF NOT EXISTS ix_scan_logs_student_id ON scan_logs(student_id)",
    "CREATE INDEX IF NOT EXISTS ix_scan_logs_doctor_id ON scan_logs(doctor_id)",
    "CREATE INDEX IF NOT EXISTS ix_scan_logs_scan_type ON scan_logs(scan_type)",
    "CREATE INDEX IF NOT EXISTS ix_scan_logs_success ON scan_logs(success)",
    "CREATE INDEX IF NOT EXISTS ix_scan_logs_hashed_uid ON scan_logs(hashed_uid)",
    "CREATE INDEX IF NOT EXISTS ix_scan_logs_device_id ON scan_logs(device_id)",
]

DEFAULT_SETTINGS = [
    ("sim_time_mode", "off", "Time simulation mode: off | freeze | offset"),
    ("sim_time_frozen_at", "", "ISO datetime to freeze at (when mode=freeze)"),
    ("sim_time_offset_seconds", "0", "Offset in seconds (when mode=offset)"),
]


def run(db_path=None):
    path = db_path or DB_PATH
    if not os.path.exists(path):
        print(f"[migration 002] DB not found at {path}; skipping.")
        return False
    conn = sqlite3.connect(path)
    try:
        conn.execute(CREATE_SCAN_LOGS)
        for sql in INDEXES:
            conn.execute(sql)

        now = datetime.utcnow().isoformat()
        for key, value, desc in DEFAULT_SETTINGS:
            conn.execute(
                """INSERT OR IGNORE INTO settings (key, value, description, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (key, value, desc, now),
            )

        conn.commit()
        print("[migration 002] scan_logs table + sim-time settings OK.")
        return True
    except Exception as e:
        print(f"[migration 002] ERROR: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    run()
