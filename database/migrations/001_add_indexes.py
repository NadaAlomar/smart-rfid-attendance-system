import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "attendance.db")

indexes = [
    "CREATE INDEX IF NOT EXISTS ix_att_session_id ON attendance_records(session_id)",
    "CREATE INDEX IF NOT EXISTS ix_att_student_id ON attendance_records(student_id)",
    "CREATE INDEX IF NOT EXISTS ix_enr_student_id ON enrollments(student_id)",
    "CREATE INDEX IF NOT EXISTS ix_enr_course_id ON enrollments(course_id)",
    "CREATE INDEX IF NOT EXISTS ix_sess_course_id ON attendance_sessions(course_id)",
    "CREATE INDEX IF NOT EXISTS ix_sess_is_active ON attendance_sessions(is_active)",
]

if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    for sql in indexes:
        try:
            conn.execute(sql)
            print(f"OK: {sql.split('IX_')[1].split(' ')[0] if 'IX_' in sql else sql}")
        except Exception as e:
            print(f"SKIP: {e}")
    conn.commit()
    conn.close()
    print("Migration complete.")
else:
    print("Database not found. Run init_database.py first.")
