"""Migration 005: Add audit_logs, role_labels tables and teaching_type column."""
from sqlalchemy import create_engine, text, inspect
import config


def run():
    engine = create_engine(f"sqlite:///{config.DATABASE_PATH}")
    inspector = inspect(engine)

    with engine.connect() as conn:
        # ── audit_logs ──
        if "audit_logs" not in inspector.get_table_names():
            conn.execute(text("""
                CREATE TABLE audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    user_id INTEGER,
                    username VARCHAR(100),
                    role VARCHAR(30),
                    action VARCHAR(50) NOT NULL,
                    entity_type VARCHAR(50) NOT NULL,
                    entity_id INTEGER,
                    entity_label VARCHAR(200),
                    changes_json TEXT,
                    ip_address VARCHAR(50),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """))
            for idx_col in ["timestamp", "user_id", "action", "entity_type", "entity_id"]:
                conn.execute(text(
                    f"CREATE INDEX IF NOT EXISTS ix_audit_logs_{idx_col} ON audit_logs({idx_col})"
                ))
            conn.commit()
            print("[Migration 005] Created audit_logs table")

        # ── role_labels ──
        if "role_labels" not in inspector.get_table_names():
            conn.execute(text("""
                CREATE TABLE role_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_key VARCHAR(30) UNIQUE NOT NULL,
                    label_ar VARCHAR(100) NOT NULL,
                    label_en VARCHAR(100) NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                INSERT INTO role_labels (role_key, label_ar, label_en) VALUES
                ('dean', 'العميدة', 'Dean'),
                ('dean_assistant', 'نائب العميدة', 'Dean Assistant'),
                ('secretary', 'السكرتيرة', 'Secretary'),
                ('doctor', 'الدكتور', 'Doctor')
            """))
            conn.commit()
            print("[Migration 005] Created role_labels table with defaults")

        # ── teaching_type on doctors ──
        doctors_cols = [c["name"] for c in inspector.get_columns("doctors")]
        if "teaching_type" not in doctors_cols:
            conn.execute(text(
                "ALTER TABLE doctors ADD COLUMN teaching_type VARCHAR(20) DEFAULT 'theory'"
            ))
            conn.commit()
            print("[Migration 005] Added teaching_type column to doctors")

    engine.dispose()
    print("[Migration 005] Done")


if __name__ == "__main__":
    run()