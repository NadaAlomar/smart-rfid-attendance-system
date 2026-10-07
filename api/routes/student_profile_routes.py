"""Profile endpoints for the secretary's "swipe-card-to-open-profile" flow.

- GET  /api/students/by-uid?uid=<raw>     → lookup a student by raw RFID UID
- GET  /api/students/<id>/profile-bundle  → full bundle (info + courses + schedule + stats)
- GET  /api/students/<id>/schedule        → weekly schedule rows
- GET  /api/students/<id>/enrollments     → enrolled courses
- POST /api/enrollments                   → already exists in management_routes (kept)
"""
from flask import Blueprint, request, jsonify
from sqlalchemy import desc

from database import get_session
from database.models import (
    Student, Branch, Course, Enrollment, Schedule, Hall,
    AttendanceSession, AttendanceRecord, Doctor,
)
from security.security_manager import hash_rfid_uid
from api.auth import require_role


PLACEHOLDER_CARD_PREFIX = "__PLACEHOLDER__"


def _card_hint(hashed_uid):
    if not hashed_uid or str(hashed_uid).startswith(PLACEHOLDER_CARD_PREFIX):
        return None
    return str(hashed_uid)[-4:]


def _is_placeholder(hashed_uid):
    return bool(hashed_uid and str(hashed_uid).startswith(PLACEHOLDER_CARD_PREFIX))


profile_bp = Blueprint("student_profile", __name__)


def _student_basic(db, student):
    branch = db.query(Branch).filter_by(id=student.branch_id).first() \
        if student.branch_id else None
    return {
        "id": student.id,
        "academic_id": student.academic_id,
        "full_name": student.full_name,
        "first_name": student.first_name,
        "father_name": student.father_name,
        "mother_name": student.mother_name,
        "last_name": student.last_name,
        "branch_id": student.branch_id,
        "branch_name": branch.branch_name if branch else None,
        "is_temporary": student.is_temporary_card,
        "expiry_date": student.card_expiry_date.isoformat()
            if student.card_expiry_date else None,
        "card_hint": _card_hint(student.hashed_uid),
        "is_placeholder_card": _is_placeholder(student.hashed_uid),
    }


def _student_courses(db, student_id):
    out = []
    enrollments = db.query(Enrollment).filter_by(student_id=student_id).all()
    for e in enrollments:
        c = db.query(Course).filter_by(id=e.course_id).first()
        if not c:
            continue
        doctor = db.query(Doctor).filter_by(id=c.doctor_id).first() \
            if c.doctor_id else None
        out.append({
            "enrollment_id": e.id,
            "course_id": c.id,
            "course_code": c.course_code,
            "course_name": c.course_name,
            "course_type": c.course_type,
            "doctor_name": doctor.full_name if doctor else "—",
        })
    return out


def _student_schedule(db, student_id):
    """List of weekly schedule rows for all courses the student is enrolled in."""
    out = []
    course_ids = [e.course_id for e in
                  db.query(Enrollment).filter_by(student_id=student_id).all()]
    if not course_ids:
        return out
    schedules = db.query(Schedule).filter(Schedule.course_id.in_(course_ids)).all()
    for sch in schedules:
        course = db.query(Course).filter_by(id=sch.course_id).first()
        hall = db.query(Hall).filter_by(id=sch.hall_id).first()
        out.append({
            "schedule_id": sch.id,
            "day_of_week": sch.day_of_week,
            "start_time": sch.start_time.strftime("%H:%M") if sch.start_time else "",
            "end_time": sch.end_time.strftime("%H:%M") if sch.end_time else "",
            "course_code": course.course_code if course else "",
            "course_name": course.course_name if course else "",
            "hall_name": hall.hall_name if hall else "—",
        })
    return out


def _student_attendance_stats(db, student_id):
    """Per-course attendance stats (only closed sessions count toward total)."""
    out = []
    enrollments = db.query(Enrollment).filter_by(student_id=student_id).all()
    for enr in enrollments:
        course = db.query(Course).filter_by(id=enr.course_id).first()
        if not course:
            continue
        total = db.query(AttendanceSession).filter(
            AttendanceSession.course_id == course.id,
            AttendanceSession.is_active == False,
        ).count()
        attended = (db.query(AttendanceRecord)
                    .join(AttendanceSession,
                          AttendanceRecord.session_id == AttendanceSession.id)
                    .filter(AttendanceRecord.student_id == student_id,
                            AttendanceSession.course_id == course.id,
                            AttendanceRecord.status == "present")
                    .count())
        absent = (db.query(AttendanceRecord)
                  .join(AttendanceSession,
                        AttendanceRecord.session_id == AttendanceSession.id)
                  .filter(AttendanceRecord.student_id == student_id,
                          AttendanceSession.course_id == course.id,
                          AttendanceRecord.status == "absent")
                  .count())
        pct = round((attended / total * 100), 1) if total > 0 else 100.0
        out.append({
            "course_id": course.id,
            "course_code": course.course_code,
            "course_name": course.course_name,
            "total_sessions": total,
            "attended": attended,
            "absent": absent,
            "percentage": pct,
        })
    return out


@profile_bp.route("/api/students/by-uid", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary")
def student_by_uid():
    uid = (request.args.get("uid") or "").strip()
    if not uid:
        return jsonify({"success": False, "error": "uid required"}), 400
    try:
        hashed = hash_rfid_uid(uid)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

    db = get_session()
    try:
        student = db.query(Student).filter_by(hashed_uid=hashed).first()
        if not student:
            # هل هي بطاقة دكتور بالخطأ؟
            doc = db.query(Doctor).filter_by(hashed_uid=hashed).first()
            if doc:
                return jsonify({
                    "success": False,
                    "error": "doctor_card",
                    "message": f"هذه بطاقة دكتور: {doc.full_name}",
                }), 404
            return jsonify({
                "success": False,
                "error": "unknown_card",
                "message": "البطاقة غير مسجّلة لأي طالب",
            }), 404
        return jsonify({"success": True, "student": _student_basic(db, student)})
    finally:
        db.close()


@profile_bp.route("/api/students/<int:student_id>/profile-bundle", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def student_profile_bundle(student_id):
    db = get_session()
    try:
        student = db.query(Student).filter_by(id=student_id).first()
        if not student:
            return jsonify({"success": False, "error": "Student not found"}), 404

        return jsonify({
            "success": True,
            "student": _student_basic(db, student),
            "courses": _student_courses(db, student_id),
            "schedule": _student_schedule(db, student_id),
            "stats": _student_attendance_stats(db, student_id),
        })
    finally:
        db.close()


@profile_bp.route("/api/students/<int:student_id>/schedule", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def student_schedule(student_id):
    db = get_session()
    try:
        return jsonify({"success": True, "schedule": _student_schedule(db, student_id)})
    finally:
        db.close()


@profile_bp.route("/api/students/<int:student_id>/enrollments", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def student_enrollments_list(student_id):
    db = get_session()
    try:
        return jsonify({"success": True, "enrollments": _student_courses(db, student_id)})
    finally:
        db.close()
