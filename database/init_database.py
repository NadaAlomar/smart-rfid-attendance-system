import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, get_engine, get_session
from database.models import (
    User, Branch, Student, Doctor, Course,
    Enrollment, Hall, Device, Schedule,
    AttendanceSession, AttendanceRecord, Alert,
    Holiday, AbsenceJustification, Setting,
    UserSession, DoctorNote,
)
from security.security_manager import hash_password, generate_device_token
import config


def migrate_schema():
    """يضيف أعمدة جديدة للجداول الموجودة"""
    from sqlalchemy import inspect, text
    engine = get_engine()
    inspector = inspect(engine)

    # students: name parts
    if "students" in inspector.get_table_names():
        cols = [c["name"] for c in inspector.get_columns("students")]
        with engine.connect() as conn:
            for col, coltype in [
                ("first_name", "VARCHAR(80)"),
                ("father_name", "VARCHAR(80)"),
                ("mother_name", "VARCHAR(80)"),
                ("last_name", "VARCHAR(80)"),
            ]:
                if col not in cols:
                    conn.execute(text(f"ALTER TABLE students ADD COLUMN {col} {coltype}"))
                    conn.commit()
                    print(f"  + students.{col}")

    # doctors: name parts
    if "doctors" in inspector.get_table_names():
        cols = [c["name"] for c in inspector.get_columns("doctors")]
        with engine.connect() as conn:
            for col, coltype in [
                ("first_name", "VARCHAR(80)"),
                ("last_name", "VARCHAR(80)"),
            ]:
                if col not in cols:
                    conn.execute(text(f"ALTER TABLE doctors ADD COLUMN {col} {coltype}"))
                    conn.commit()
                    print(f"  + doctors.{col}")

    # courses: branch_id
    if "courses" in inspector.get_table_names():
        cols = [c["name"] for c in inspector.get_columns("courses")]
        with engine.connect() as conn:
            if "branch_id" not in cols:
                conn.execute(text("ALTER TABLE courses ADD COLUMN branch_id INTEGER"))
                conn.commit()
                print(f"  + courses.branch_id")


def create_database():
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    print("تم إنشاء جداول قاعدة البيانات بنجاح!")
    migrate_schema()


def create_admin_user():
    session = get_session()
    try:
        admin = session.query(User).filter_by(username="admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="dean",
            )
            session.add(admin)
            session.commit()
            print("تم إنشاء حساب العميدة: admin / admin123")
        else:
            print("حساب العميدة موجود مسبقاً")

        secretary = session.query(User).filter_by(username="secretary").first()
        if not secretary:
            secretary = User(
                username="secretary",
                password_hash=hash_password("secretary123"),
                role="secretary",
            )
            session.add(secretary)
            session.commit()
            print("تم إنشاء حساب السكرتارية: secretary / secretary123")
    except Exception as e:
        session.rollback()
        print(f"خطأ في إنشاء المستخدمين: {e}")
    finally:
        session.close()


def run_migrations():
    try:
        from database.migrations import run_all
        run_all()
    except Exception:
        from database.migrations import run_all as _run
        _run()


def insert_sample_data():
    session = get_session()
    try:
        if session.query(Branch).count() > 0:
            print("البيانات التجريبية موجودة مسبقاً، تم التخطي.")
            return

        # الأقسام
        branch1 = Branch(branch_name="هندسة المعلوماتية", branch_code="IT")
        branch2 = Branch(branch_name="علوم الحاسوب", branch_code="CS")
        session.add_all([branch1, branch2])
        session.flush()

        # القاعات
        hall1 = Hall(hall_name="قاعة A", hall_type="theory")
        hall2 = Hall(hall_name="قاعة B", hall_type="theory")
        hall3 = Hall(hall_name="مختبر 1", hall_type="practical")
        session.add_all([hall1, hall2, hall3])
        session.flush()

        # الأجهزة — only if not already exist
        if not session.query(Device).filter_by(device_id="DEVICE001").first():
            session.add(Device(
                device_id="DEVICE001",
                hall_id=hall1.id,
                device_token=generate_device_token(),
                is_active=True,
            ))
        if not session.query(Device).filter_by(device_id="DEVICE002").first():
            session.add(Device(
                device_id="DEVICE002",
                hall_id=hall2.id,
                device_token=generate_device_token(),
                is_active=True,
            ))

        # المواد
        course1 = Course(
            course_code="IT101",
            course_name="مقدمة في هندسة المعلوماتية",
            course_type="theory",
            total_weeks=15,
        )
        course2 = Course(
            course_code="IT102",
            course_name="أنظمة المعلومات",
            course_type="theory",
            total_weeks=15,
        )
        session.add_all([course1, course2])

        session.commit()
        print("تم إدخال البيانات التجريبية بنجاح!")
    except Exception as e:
        session.rollback()
        print(f"خطأ في إدخال البيانات التجريبية: {e}")
    finally:
        session.close()


def seed_settings():
    session = get_session()
    try:
        if not session.query(Setting).filter_by(key="session_timeout_minutes").first():
            session.add(Setting(
                key="session_timeout_minutes",
                value=str(config.SESSION_TIMEOUT_MINUTES),
                description="زمن الإغلاق التلقائي للجلسة بالدقائق",
            ))
            session.commit()
            print("تم إضافة إعدادات الجلسة الافتراضية")
    except Exception as e:
        session.rollback()
        print(f"خطأ في إضافة الإعدادات: {e}")
    finally:
        session.close()


def main():
    print("=" * 50)
    print("  تهيئة قاعدة بيانات نظام الحضور الجامعي")
    print("=" * 50)
    create_database()
    create_admin_user()
    insert_sample_data()
    seed_settings()
    import importlib
    m = importlib.import_module("database.migrations.003_add_roles_and_notes")
    m.run()
    print("=" * 50)
    print("  اكتملت عملية التهيئة بنجاح!")
    print("  بيانات الدخول: admin / admin123")
    print("=" * 50)


if __name__ == "__main__":
    main()
