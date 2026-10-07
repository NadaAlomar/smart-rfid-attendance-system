"""Migration 006: Add qr_sessions table for QR-based attendance."""
from sqlalchemy import create_engine, text, inspect
import config


def run():
    engine = create_engine(f"sqlite:///{config.DATABASE_PATH}")
    inspector = inspect(engine)

    with engine.connect() as conn:
        if "qr_sessions" not in inspector.get_table_names():
            conn.execute(text("""
                CREATE TABLE qr_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attendance_session_id INTEGER NOT NULL,
                    doctor_id INTEGER NOT NULL,
                    course_id INTEGER,
                    hall_id INTEGER,
                    current_token VARCHAR(64) NOT NULL,
                    token_rotates_at DATETIME NOT NULL,
                    session_expires_at DATETIME NOT NULL,
                    is_active BOOLEAN DEFAULT 1 NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (attendance_session_id) REFERENCES attendance_sessions(id),
                    FOREIGN KEY (doctor_id) REFERENCES doctors(id),
                    FOREIGN KEY (course_id) REFERENCES courses(id),
                    FOREIGN KEY (hall_id) REFERENCES halls(id)
                )
            """))
            for idx_col in ["attendance_session_id", "doctor_id", "current_token", "is_active"]:
                conn.execute(text(
                    f"CREATE INDEX IF NOT EXISTS ix_qr_sessions_{idx_col} ON qr_sessions({idx_col})"
                ))
            conn.commit()
            print("[Migration 006] Created qr_sessions table")
        else:
            print("[Migration 006] qr_sessions already exists, skipping")

    engine.dispose()
    print("[Migration 006] Done")


if __name__ == "__main__":
    run()
