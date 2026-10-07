from database import get_session
from database.models import (
    Alert, Student, Course, AttendanceRecord,
    AttendanceSession, Enrollment, AbsenceJustification, Setting,
)
from sqlalchemy import or_
from datetime import datetime

# عتبة الغياب التي تُولّد تنبيهاً (≈ 4 أسابيع لمادة أسبوعية)
ABSENCE_ALERT_THRESHOLD = 4


# ────────────────────────── إعدادات ──────────────────────────
def get_setting(key, default=None):
    s = get_session()
    try:
        row = s.query(Setting).filter_by(key=key).first()
        return row.value if row else default
    finally:
        s.close()


def auto_alerts_enabled():
    """التنبيهات التلقائية مفعّلة افتراضياً؛ يمكن إطفاؤها من الإعدادات."""
    val = get_setting("auto_alerts_enabled", "1")
    return str(val).strip().lower() not in ("0", "false", "off", "no", "")


# ────────────────────────── حساب الغياب ──────────────────────────
def get_student_absences(student_id, course_id, exclude_justified=True):
    """عدد غيابات الطالب في مادة.

    التصحيح: تُحسب الجلسات المغلقة التي ليس للطالب فيها تسجيل حضور (present).
    سابقاً كان النظام يَعُدّ كل سجلات الطالب (حضور + غياب) كأنها حضور، فكانت
    النتيجة دائماً صفراً ولا يُولَّد أي تنبيه. كما تُستثنى الجلسات المُبرّرة.
    """
    session = get_session()
    try:
        closed = session.query(AttendanceSession).filter(
            AttendanceSession.course_id == course_id,
            AttendanceSession.is_active == False,
        ).all()
        if not closed:
            return 0
        closed_ids = [s.id for s in closed]

        present_session_ids = {
            r.session_id for r in session.query(AttendanceRecord).filter(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.status == "present",
                AttendanceRecord.session_id.in_(closed_ids),
            ).all()
        }
        absent_sessions = [s for s in closed if s.id not in present_session_ids]
        if not exclude_justified or not absent_sessions:
            return len(absent_sessions)

        justs = session.query(AbsenceJustification).filter(
            AbsenceJustification.student_id == student_id,
            or_(AbsenceJustification.course_id == course_id,
                AbsenceJustification.course_id.is_(None)),
        ).all()

        def _justified(d):
            return any(j.from_date <= d <= j.to_date for j in justs)

        unjustified = [s for s in absent_sessions if not _justified(s.session_date)]
        return len(unjustified)
    finally:
        session.close()


def calculate_attendance_percentage(student_id, course_id):
    session = get_session()
    try:
        total = (
            session.query(AttendanceSession)
            .filter(
                AttendanceSession.course_id == course_id,
                AttendanceSession.is_active == False,
            )
            .count()
        )
        if total == 0:
            return 100.0
        attended = (
            session.query(AttendanceRecord)
            .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
            .filter(
                AttendanceRecord.student_id == student_id,
                AttendanceSession.course_id == course_id,
                AttendanceSession.is_active == False,
                AttendanceRecord.status == "present",
            )
            .count()
        )
        return round((attended / total) * 100, 1)
    finally:
        session.close()


def check_attendance_alerts():
    """يفحص كل التسجيلات ويُنشئ التنبيهات الناقصة. يعمل تلقائياً ما لم يُطفأ."""
    if not auto_alerts_enabled():
        return 0, "auto alerts disabled"

    session = get_session()
    try:
        enrollments = session.query(Enrollment).all()
        created = 0

        for enrollment in enrollments:
            student_id = enrollment.student_id
            course_id = enrollment.course_id
            absences = get_student_absences(student_id, course_id)
            pct = calculate_attendance_percentage(student_id, course_id)

            checks = []
            if absences >= ABSENCE_ALERT_THRESHOLD:
                checks.append("4_absences")
            if pct == 0:
                checks.append("zero_attendance")
            elif pct < 25:
                checks.append("low_percent")

            for alert_type in checks:
                exists = session.query(Alert).filter_by(
                    student_id=student_id,
                    course_id=course_id,
                    alert_type=alert_type,
                    is_read=False,
                ).first()
                if not exists:
                    session.add(Alert(
                        student_id=student_id,
                        course_id=course_id,
                        alert_type=alert_type,
                    ))
                    created += 1

        session.commit()
        return created, f"Generated {created} alerts"
    except Exception as e:
        session.rollback()
        return 0, f"Error: {str(e)}"
    finally:
        session.close()


def get_active_alerts(limit=100):
    session = get_session()
    try:
        alerts = (
            session.query(Alert)
            .filter_by(is_read=False)
            .order_by(Alert.alert_date.desc())
            .limit(limit)
            .all()
        )
        result = []
        for alert in alerts:
            student = session.query(Student).filter_by(id=alert.student_id).first()
            course = session.query(Course).filter_by(id=alert.course_id).first()
            absences = get_student_absences(alert.student_id, alert.course_id) if course else 0
            result.append({
                "id": alert.id,
                "student_id": student.academic_id if student else None,
                "student_name": student.full_name if student else None,
                "course_name": course.course_name if course else None,
                "alert_type": alert.alert_type,
                "absences": absences,
                "alert_date": alert.alert_date.isoformat(),
                "is_read": alert.is_read,
            })
        return result
    finally:
        session.close()


def mark_alert_as_read(alert_id):
    session = get_session()
    try:
        alert = session.query(Alert).filter_by(id=alert_id).first()
        if not alert:
            return False, "Alert not found"
        alert.is_read = True
        session.commit()
        return True, "Alert marked as read"
    except Exception as e:
        session.rollback()
        return False, f"Error: {str(e)}"
    finally:
        session.close()


def generate_weekly_report(course_id, week_number):
    session = get_session()
    try:
        from utils.date_utils import get_date_range_for_week

        week_start, week_end = get_date_range_for_week(week_number)
        course = session.query(Course).filter_by(id=course_id).first()
        if not course:
            return None, "Course not found"

        enrollments = session.query(Enrollment).filter_by(course_id=course_id).all()
        report = []

        for enr in enrollments:
            student = session.query(Student).filter_by(id=enr.student_id).first()
            if not student:
                continue

            sessions = (
                session.query(AttendanceSession)
                .filter(
                    AttendanceSession.course_id == course_id,
                    AttendanceSession.session_date >= week_start,
                    AttendanceSession.session_date <= week_end,
                )
                .all()
            )

            attendance = []
            for sess in sessions:
                record = session.query(AttendanceRecord).filter_by(
                    session_id=sess.id, student_id=student.id
                ).first()
                attendance.append({
                    "date": sess.session_date.isoformat(),
                    "status": "present" if (record and record.status == "present") else "absent",
                })

            report.append({
                "student_id": student.academic_id,
                "student_name": student.full_name,
                "attendance": attendance,
                "percentage": calculate_attendance_percentage(student.id, course_id),
            })

        return report, "Report generated"
    except Exception as e:
        return None, f"Error: {str(e)}"
    finally:
        session.close()
