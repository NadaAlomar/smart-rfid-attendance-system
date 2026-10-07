from database import get_session
from database.models import (
    AttendanceSession, AttendanceRecord, Student,
    Course, Schedule, Hall, Doctor, Device, Enrollment,
)
from datetime import datetime
import config
from utils.date_utils import is_session_expired
from utils.time_provider import now as tp_now, today as tp_today


def open_session(doctor_id, schedule_id=None, hall_id=None, course_id=None):
    session = get_session()
    try:
        # ─── فحص العطلة لليوم ───
        from database.models import Holiday
        today = tp_today()
        holiday = session.query(Holiday).filter_by(holiday_date=today).first()
        if holiday:
            return None, f"اليوم عطلة ({holiday.holiday_name}). لا يمكن فتح جلسة."

        active = session.query(AttendanceSession).filter_by(
            doctor_id=doctor_id, is_active=True
        ).first()
        if active:
            return None, "Doctor already has an active session"

        resolved_course_id = course_id
        if not resolved_course_id and schedule_id:
            sched = session.query(Schedule).filter_by(id=schedule_id).first()
            if sched:
                resolved_course_id = sched.course_id

        new_session = AttendanceSession(
            schedule_id=schedule_id,
            course_id=resolved_course_id,
            doctor_id=doctor_id,
            session_date=tp_today(),
            start_timestamp=tp_now(),
            is_active=True,
        )
        session.add(new_session)
        session.commit()
        session.refresh(new_session)

        # تنبيه الواجهة
        try:
            from api.routes.scanner_routes import _bump_live_counter
            _bump_live_counter({"type": "session_opened",
                                 "session_id": new_session.id,
                                 "doctor_id": doctor_id})
        except Exception:
            pass

        return new_session.id, "Session opened successfully"

    except Exception as e:
        session.rollback()
        return None, f"Error opening session: {str(e)}"
    finally:
        session.close()


def close_session(session_id):
    session = get_session()
    try:
        active = session.query(AttendanceSession).filter_by(
            id=session_id, is_active=True
        ).first()
        if not active:
            return False, "No active session found"

        active.is_active = False
        active.end_timestamp = tp_now()

        enrolled = session.query(Enrollment).filter_by(course_id=active.course_id).all()
        for enr in enrolled:
            existing = session.query(AttendanceRecord).filter_by(
                session_id=active.id, student_id=enr.student_id
            ).first()
            if not existing:
                session.add(AttendanceRecord(
                    session_id=active.id,
                    student_id=enr.student_id,
                    check_in_time=tp_now(),
                    status="absent",
                ))
        session.commit()

        try:
            from api.routes.scanner_routes import _bump_live_counter
            _bump_live_counter({"type": "session_closed",
                                 "session_id": session_id})
        except Exception:
            pass

        try:
            from api.controllers.alert_controller import check_attendance_alerts
            import threading
            threading.Thread(target=check_attendance_alerts, daemon=True).start()
        except Exception:
            pass

        return True, "Session closed successfully"

    except Exception as e:
        session.rollback()
        return False, f"Error closing session: {str(e)}"
    finally:
        session.close()


def record_attendance(session_id, student_id):
    session = get_session()
    try:
        existing = session.query(AttendanceRecord).filter_by(
            session_id=session_id, student_id=student_id
        ).first()
        if existing:
            return None, "Duplicate scan detected"

        record = AttendanceRecord(
            session_id=session_id,
            student_id=student_id,
            check_in_time=tp_now(),
            status="present",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        try:
            from api.routes.scanner_routes import _bump_live_counter
            _bump_live_counter({"type": "attendance_recorded",
                                 "session_id": session_id,
                                 "student_id": student_id})
        except Exception:
            pass

        return record.id, "Attendance recorded successfully"

    except Exception as e:
        session.rollback()
        return None, f"Error recording attendance: {str(e)}"
    finally:
        session.close()


def check_duplicate_scan(session_id, student_id):
    session = get_session()
    try:
        return (
            session.query(AttendanceRecord)
            .filter_by(session_id=session_id, student_id=student_id)
            .first()
            is not None
        )
    finally:
        session.close()


def get_active_session_for_hall(hall_id):
    session = get_session()
    try:
        return (
            session.query(AttendanceSession)
            .join(Schedule, AttendanceSession.schedule_id == Schedule.id)
            .filter(Schedule.hall_id == hall_id, AttendanceSession.is_active == True)
            .first()
        )
    finally:
        session.close()


def get_active_session_for_doctor(doctor_id):
    session = get_session()
    try:
        return (
            session.query(AttendanceSession)
            .filter_by(doctor_id=doctor_id, is_active=True)
            .first()
        )
    finally:
        session.close()


def auto_close_sessions():
    session = get_session()
    try:
        active = session.query(AttendanceSession).filter_by(is_active=True).all()
        closed = 0
        for s in active:
            if is_session_expired(s.start_timestamp):
                s.is_active = False
                s.end_timestamp = tp_now()

                enrolled_q = session.query(Enrollment).filter_by(course_id=s.course_id).all()
                for enr in enrolled_q:
                    existing = session.query(AttendanceRecord).filter_by(
                        session_id=s.id, student_id=enr.student_id
                    ).first()
                    if not existing:
                        session.add(AttendanceRecord(
                            session_id=s.id,
                            student_id=enr.student_id,
                            check_in_time=tp_now(),
                            status="absent",
                        ))
                closed += 1
        session.commit()

        if closed > 0:
            try:
                from api.controllers.alert_controller import check_attendance_alerts
                import threading
                threading.Thread(target=check_attendance_alerts, daemon=True).start()
            except Exception:
                pass

        return closed, f"Auto-closed {closed} sessions"
    except Exception as e:
        session.rollback()
        return 0, f"Error: {str(e)}"
    finally:
        session.close()


def get_attendance_stats(session_id):
    session = get_session()
    try:
        records = session.query(AttendanceRecord).filter_by(session_id=session_id).all()
        total = len(records)
        present = sum(1 for r in records if r.status == "present")
        return {
            "total": total,
            "present": present,
            "absent": total - present,
            "percentage": round((present / total * 100), 1) if total > 0 else 0,
        }
    finally:
        session.close()


# ════════════════════════════════════════════════════════════════════
#  توليد الجلسات المستحقّة حتى التاريخ الحالي (يدعم محاكاة الوقت المحلي)
#  الغاية: عند تفعيل "الوقت المحلي" والتقدّم 4 أسابيع، تُنشأ الجلسات
#  الأسبوعية الفائتة كجلسات مغلقة مع تسجيل غياب للطلاب غير الحاضرين،
#  ثم يُفحص توليد التنبيهات (للسكرتارية والعميدة ونائبها).
# ════════════════════════════════════════════════════════════════════
def _get_or_init_semester_start(session):
    from database.models import Setting
    row = session.query(Setting).filter_by(key="semester_start_date").first()
    if row and row.value:
        try:
            return datetime.strptime(row.value, "%Y-%m-%d").date()
        except ValueError:
            pass
    # أول مرة: ابدأ من تاريخ اليوم الحقيقي (ساعة الجدار) لا الوقت المُحاكى
    start = datetime.now().date()
    if row:
        row.value = start.isoformat()
    else:
        session.add(Setting(key="semester_start_date", value=start.isoformat(),
                            description="بداية الفصل الدراسي (لتوليد الجلسات المستحقة)"))
    session.commit()
    return start


def materialize_due_sessions(up_to=None):
    """ينشئ الجلسات الأسبوعية المستحقّة حتى up_to (افتراضياً الوقت الحالي/المُحاكى)."""
    from datetime import timedelta
    from database.models import Schedule, Holiday, Setting

    session = get_session()
    try:
        if up_to is None:
            up_to = tp_today()

        # هل التوليد التلقائي مفعّل؟ (نفس مفتاح التنبيهات التلقائية)
        row = session.query(Setting).filter_by(key="auto_alerts_enabled").first()
        if row and str(row.value).strip().lower() in ("0", "false", "off", "no"):
            return 0, "auto generation disabled"

        start = _get_or_init_semester_start(session)
        if up_to < start:
            return 0, "nothing due"

        holidays = {h.holiday_date for h in session.query(Holiday).all()}
        schedules = session.query(Schedule).all()
        # مواد لها طلاب مسجّلون فقط
        from database.models import Enrollment
        enrolled_course_ids = {e.course_id for e in session.query(Enrollment).all()}

        created_sessions = 0
        for sched in schedules:
            if sched.course_id not in enrolled_course_ids:
                continue
            # امشِ على كل تاريخ من البداية حتى up_to، خذ ما يطابق يوم الأسبوع
            d = start
            while d <= up_to:
                if d.weekday() == sched.day_of_week and d not in holidays:
                    exists = session.query(AttendanceSession).filter(
                        AttendanceSession.course_id == sched.course_id,
                        AttendanceSession.session_date == d,
                    ).first()
                    if not exists:
                        # دكتور المادة (إن وُجد) — مطلوب لأن doctor_id غير قابل للإفراغ
                        from database.models import Course
                        course = session.query(Course).filter_by(id=sched.course_id).first()
                        doctor_id = course.doctor_id if course and course.doctor_id else None
                        if doctor_id is None:
                            # لا يمكن إنشاء جلسة بلا دكتور — تخطَّ هذه المادة
                            d += timedelta(days=1)
                            continue
                        new_sess = AttendanceSession(
                            schedule_id=sched.id,
                            course_id=sched.course_id,
                            doctor_id=doctor_id,
                            session_date=d,
                            start_timestamp=datetime.combine(d, sched.start_time),
                            end_timestamp=datetime.combine(d, sched.end_time),
                            is_active=False,
                        )
                        session.add(new_sess)
                        session.flush()
                        # سجّل غياب الطلاب غير الحاضرين
                        enrolled = session.query(Enrollment).filter_by(
                            course_id=sched.course_id).all()
                        for enr in enrolled:
                            session.add(AttendanceRecord(
                                session_id=new_sess.id,
                                student_id=enr.student_id,
                                check_in_time=datetime.combine(d, sched.end_time),
                                status="absent",
                            ))
                        created_sessions += 1
                d += timedelta(days=1)

        session.commit()

        if created_sessions > 0:
            try:
                from api.controllers.alert_controller import check_attendance_alerts
                check_attendance_alerts()
            except Exception:
                pass

        return created_sessions, f"Materialized {created_sessions} due sessions"
    except Exception as e:
        session.rollback()
        return 0, f"Error: {str(e)}"
    finally:
        session.close()
