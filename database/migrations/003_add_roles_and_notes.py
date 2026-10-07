"""Migration 003: user_sessions + doctor_notes tables + default role accounts.

Idempotent: safe to run multiple times.
"""
import sqlite3
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "attendance.db")


CREATE_USER_SESSIONS = """
CREATE TABLE IF NOT EXISTS user_sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    token      VARCHAR(128) NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    last_seen  DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_DOCTOR_NOTES = """
CREATE TABLE IF NOT EXISTS doctor_notes (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id            INTEGER NOT NULL REFERENCES doctors(id),
    student_id           INTEGER NOT NULL REFERENCES students(id),
    course_id            INTEGER REFERENCES courses(id),
    note                 TEXT NOT NULL,
    severity             VARCHAR(20) DEFAULT 'info',
    is_read_by_secretary BOOLEAN DEFAULT 0,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

SESSION_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS ix_user_sessions_token ON user_sessions(token)",
]

NOTES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_doctor_notes_doctor_id ON doctor_notes(doctor_id)",
    "CREATE INDEX IF NOT EXISTS ix_doctor_notes_student_id ON doctor_notes(student_id)",
    "CREATE INDEX IF NOT EXISTS ix_doctor_notes_course_id ON doctor_notes(course_id)",
    "CREATE INDEX IF NOT EXISTS ix_doctor_notes_is_read ON doctor_notes(is_read_by_secretary)",
]

DEFAULT_ACCOUNTS = [
    ("dean", "dean123", "dean"),
    ("dean_assistant", "assistant123", "dean_assistant"),
]


def run(db_path=None):
    path = db_path or DB_PATH
    if not os.path.exists(path):
        print("[migration 003] DB not found; skipping.")
        return False
    conn = sqlite3.connect(path)
    try:
        conn.execute(CREATE_USER_SESSIONS)
        conn.execute(CREATE_DOCTOR_NOTES)
        for sql in SESSION_INDEXES + NOTES_INDEXES:
            conn.execute(sql)

        now = datetime.utcnow().isoformat()
        for username, password, role in DEFAULT_ACCOUNTS:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if not existing:
                from security.security_manager import hash_password
                conn.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                    (username, hash_password(password), role, now),
                )
                print(f"  + user: {username} / {password} ({role})")

        conn.commit()
        print("[migration 003] user_sessions + doctor_notes + accounts OK.")
        return True
    except Exception as e:
        print(f"[migration 003] ERROR: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    run()
