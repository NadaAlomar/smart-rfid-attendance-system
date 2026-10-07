"""Seed demo data with PLACEHOLDER cards that admins replace later.

Placeholder UIDs are stored directly as `__PLACEHOLDER__<role>_<index>` strings
in `hashed_uid` (bypassing real RFID hashing). The edit-dialog UIs detect this
prefix and show a warning badge, prompting the admin to swap in a real card.
"""
from database import get_session
from database.models import (
    Branch, Hall, Device, Doctor, Student, Course,
    Enrollment, Schedule, Holiday, Setting,
)
from security.security_manager import generate_device_token
from datetime import datetime, date, time, timedelta


PLACEHOLDER_PREFIX = "__PLACEHOLDER__"


def is_placeholder_card(hashed_uid):
    """Return True if a hashed_uid is a placeholder produced by this seeder."""
    return bool(hashed_uid) and str(hashed_uid).startswith(PLACEHOLDER_PREFIX)


ARABIC_FIRST_NAMES = [
    "أحمد", "محمد", "علي", "سارة", "ليلى", "فاطمة", "خالد", "عمر", "نور", "ياسمين",
    "حسن", "حسين", "زينب", "مريم", "يوسف", "إبراهيم", "كريم", "هدى", "رنا", "ميس",
    "بشار", "ميلاد", "جوان", "روان", "سيف", "تيم", "آدم", "لؤي", "غدير", "ربى",
]
ARABIC_FATHER_NAMES = [
    "محمد", "أحمد", "خالد", "علي", "حسن", "إبراهيم", "ياسر", "بسام", "نزار", "هيثم",
]
ARABIC_MOTHER_NAMES = [
    "فاطمة", "عائشة", "خديجة", "هدى", "أمل", "سامية", "نجلاء", "سهام", "وفاء", "رنا",
]
ARABIC_LAST_NAMES = [
    "العلي", "الحسن", "السيد", "الخطيب", "الزعبي", "النجار", "الكردي",
    "العمر", "الصالح", "الأحمد", "المصري", "الشامي",
]

DOCTOR_FIRST = ["أحمد", "سارة", "خالد", "محمد", "ليلى", "عمر", "هدى", "بشار"]
DOCTOR_LAST = [
    "الخطيب", "الزعبي", "النجار", "العلي", "السيد",
    "الكردي", "الأحمد", "الحسن",
]


def _doctor_full(first, last):
    return f"د. {first} {last}"


def seed_demo_data():
    """Create demo data. Returns a summary dict.

    If data already exists, only fills gaps (idempotent for halls/branches/devices).
    Students/doctors are created only on empty DBs to avoid duplicating placeholders.
    """
    session = get_session()
    summary = {"branches": 0, "halls": 0, "devices": 0, "doctors": 0,
               "courses": 0, "students": 0, "enrollments": 0,
               "schedules": 0, "holidays": 0, "settings": 0,
               "skipped": False}
    try:
        # ── Branches ──
        if session.query(Branch).count() == 0:
            for name, code in [("علوم الحاسوب", "CS"),
                                ("تكنولوجيا المعلومات", "IT"),
                                ("هندسة الشبكات", "NET")]:
                session.add(Branch(branch_name=name, branch_code=code))
            session.flush()
            summary["branches"] = 3
        branches = session.query(Branch).all()

        # ── Halls ──
        if session.query(Hall).count() == 0:
            for name, htype in [("A101", "theory"), ("A102", "theory"),
                                 ("B201", "theory"), ("Lab1", "lab"),
                                 ("Lab2", "lab")]:
                session.add(Hall(hall_name=name, hall_type=htype))
            session.flush()
            summary["halls"] = 5
        halls = session.query(Hall).all()

        # ── Devices ──
        if session.query(Device).count() == 0:
            for i, hall in enumerate(halls):
                session.add(Device(
                    device_id=f"DEVICE{i+1:03d}",
                    hall_id=hall.id,
                    device_token=generate_device_token(),
                    is_active=True,
                ))
            session.add(Device(
                device_id="SECRETARY",
                device_token=generate_device_token(),
                is_active=True,
            ))
            session.flush()
            summary["devices"] = 6

        # ── Doctors (8) with placeholder UIDs ──
        if session.query(Doctor).count() == 0:
            for i in range(8):
                first = DOCTOR_FIRST[i % len(DOCTOR_FIRST)]
                last = DOCTOR_LAST[i % len(DOCTOR_LAST)]
                placeholder = f"{PLACEHOLDER_PREFIX}doctor_{i+1:03d}"
                session.add(Doctor(
                    full_name=_doctor_full(first, last),
                    first_name=first,
                    last_name=last,
                    hashed_uid=placeholder,
                ))
            session.flush()
            summary["doctors"] = 8
        doctors = session.query(Doctor).all()

        # ── Courses (10) ──
        if session.query(Course).count() == 0:
            courses_data = [
                ("CS101", "مقدمة في الحاسوب", "CS", 0),
                ("CS201", "هياكل بيانات", "CS", 1),
                ("CS301", "قواعد بيانات", "CS", 2),
                ("IT101", "مقدمة تكنولوجيا معلومات", "IT", 3),
                ("IT202", "أمن معلومات", "IT", 4),
                ("NET101", "شبكات حاسوب", "NET", 5),
                ("NET202", "شبكات متقدمة", "NET", 6),
                ("MATH101", "رياضيات عامة", "CS", 7),
                ("ENG101", "لغة إنجليزية", "CS", 0),
                ("PHY101", "فيزياء عامة", "IT", 1),
            ]
            for code, name, branch_code, doc_idx in courses_data:
                branch = next((b for b in branches if b.branch_code == branch_code), branches[0])
                doc = doctors[doc_idx % len(doctors)]
                session.add(Course(
                    course_code=code, course_name=name,
                    course_type="theory", total_weeks=15,
                    doctor_id=doc.id, branch_id=branch.id,
                ))
            session.flush()
            summary["courses"] = 10
        courses = session.query(Course).all()

        # ── Students (30: 10 per branch) ──
        if session.query(Student).count() == 0:
            for branch_idx, branch in enumerate(branches):
                for j in range(10):
                    fn = ARABIC_FIRST_NAMES[(branch_idx * 10 + j) % len(ARABIC_FIRST_NAMES)]
                    father = ARABIC_FATHER_NAMES[j % len(ARABIC_FATHER_NAMES)]
                    mother = ARABIC_MOTHER_NAMES[j % len(ARABIC_MOTHER_NAMES)]
                    ln = ARABIC_LAST_NAMES[(branch_idx * 3 + j) % len(ARABIC_LAST_NAMES)]
                    full = f"{fn} {father} {ln}"
                    academic_id = f"2023{branch_idx+1}{j+1:03d}"
                    placeholder = f"{PLACEHOLDER_PREFIX}student_{branch_idx+1}_{j+1:03d}"
                    session.add(Student(
                        academic_id=academic_id, full_name=full,
                        first_name=fn, father_name=father,
                        mother_name=mother, last_name=ln,
                        hashed_uid=placeholder,
                        is_temporary_card=False,
                        branch_id=branch.id,
                    ))
            session.flush()
            summary["students"] = 30
        students = session.query(Student).all()

        # ── Enrollments (each student in 3 courses from their branch + some shared) ──
        if session.query(Enrollment).count() == 0:
            # group courses by branch
            by_branch = {}
            for c in courses:
                by_branch.setdefault(c.branch_id, []).append(c)
            shared_indices = [7, 8]  # MATH, ENG common
            enroll_count = 0
            for stu in students:
                branch_courses = by_branch.get(stu.branch_id, [])[:3]
                for c in branch_courses:
                    session.add(Enrollment(student_id=stu.id, course_id=c.id))
                    enroll_count += 1
                for si in shared_indices:
                    if si < len(courses):
                        session.add(Enrollment(student_id=stu.id, course_id=courses[si].id))
                        enroll_count += 1
            session.flush()
            summary["enrollments"] = enroll_count

        # ── Schedules (clamped to available halls/courses) ──
        if session.query(Schedule).count() == 0 and courses and halls:
            schedule_data = [
                # (course_idx, hall_idx, day_of_week, start, end)
                (0, 0, 5, "08:00", "09:30"),  # Sat
                (1, 1, 5, "10:00", "11:30"),
                (2, 2, 6, "08:00", "09:30"),  # Sun
                (3, 0, 6, "10:00", "11:30"),
                (4, 3, 0, "08:00", "09:30"),  # Mon
                (5, 4, 0, "10:00", "11:30"),
                (6, 1, 1, "08:00", "09:30"),  # Tue
                (7, 0, 2, "10:00", "11:30"),  # Wed
                (8, 1, 2, "13:00", "14:30"),
                (9, 3, 3, "13:00", "14:30"),  # Thu
            ]
            added = 0
            for cidx, hidx, day, start, end in schedule_data:
                if cidx >= len(courses) or hidx >= len(halls):
                    continue
                session.add(Schedule(
                    course_id=courses[cidx].id,
                    hall_id=halls[hidx].id,
                    day_of_week=day,
                    start_time=datetime.strptime(start, "%H:%M").time(),
                    end_time=datetime.strptime(end, "%H:%M").time(),
                ))
                added += 1
            session.flush()
            summary["schedules"] = added

        # ── Holidays ──
        if session.query(Holiday).count() == 0:
            today = date.today()
            for name, offset in [
                ("عيد الفطر", -30),
                ("عطلة نصف العام", 0),
                ("عطلة الصيف", 30),
            ]:
                session.add(Holiday(
                    holiday_date=today + timedelta(days=offset),
                    holiday_name=name, holiday_type="holiday",
                ))
            summary["holidays"] = 3

        # ── Defaults (do not overwrite existing) ──
        default_settings = [
            ("session_timeout_minutes", "15", "زمن الإغلاق التلقائي بالدقائق"),
            ("time_format", "12h", "صيغة الوقت 12h/24h"),
            ("sim_time_mode", "off", "وضع محاكاة الوقت"),
            ("sim_time_frozen_at", "", "وقت التجميد إذا mode=freeze"),
            ("sim_time_offset_seconds", "0", "إزاحة بالثواني إذا mode=offset"),
        ]
        for k, v, desc in default_settings:
            if not session.query(Setting).filter_by(key=k).first():
                session.add(Setting(key=k, value=v, description=desc))
                summary["settings"] += 1

        session.commit()

        # If nothing actually got created (all already there)
        if not any(v for k, v in summary.items() if k != "skipped"):
            summary["skipped"] = True

        # Print summary
        print("[seed] Demo seed complete:")
        for k, v in summary.items():
            print(f"  {k}: {v}")
        return summary
    except Exception as e:
        session.rollback()
        print(f"[seed] ERROR: {e}")
        raise
    finally:
        session.close()


# Backwards-compatible alias
def main():
    return seed_demo_data()


if __name__ == "__main__":
    main()
