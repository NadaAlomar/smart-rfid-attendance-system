from flask import Blueprint, request, jsonify
from database import get_session
from database.models import (
    Doctor, Student, Course, Enrollment, AttendanceSession,
    AttendanceRecord, DoctorNote, Schedule, Grade,
)
from sqlalchemy import desc
from api.auth import get_current_user, require_role

doctor_bp = Blueprint("doctor_portal", __name__)


@doctor_bp.route("/api/doctor/me/courses", methods=["GET"])
@require_role("doctor", "dean")
def my_courses():
    user = get_current_user()
    if not user or not user.get("doctor_id"):
        return jsonify({"success": False, "error": "No doctor profile"}), 403
    s = get_session()
    try:
        courses = s.query(Course).filter_by(doctor_id=user["doctor_id"]).all()
        return jsonify({
            "success": True,
            "courses": [{
                "id": c.id,
                "course_name": c.course_name,
                "course_code": c.course_code,
                "course_type": c.course_type,
                "enrollment_count": len(c.enrollments),
            } for c in courses],
        })
    finally:
        s.close()


@doctor_bp.route("/api/doctor/me/students", methods=["GET"])
@require_role("doctor", "dean")
def my_students():
    user = get_current_user()
    if not user or not user.get("doctor_id"):
        return jsonify({"success": False, "error": "No doctor profile"}), 403
    q = (request.args.get("q") or "").strip()
    s = get_session()
    try:
        course_ids = [c.id for c in s.query(Course).filter_by(doctor_id=user["doctor_id"]).all()]
        if not course_ids:
            return jsonify({"success": True, "students": []})
        enrollments = s.query(Enrollment).filter(Enrollment.course_id.in_(course_ids)).all()
        student_ids = list({e.student_id for e in enrollments})
        if not student_ids:
            return jsonify({"success": True, "students": []})
        query = s.query(Student).filter(Student.id.in_(student_ids))
        if q:
            query = query.filter(Student.full_name.ilike(f"%{q}%"))
        students = query.all()
        return jsonify({
            "success": True,
            "students": [{
                "id": st.id,
                "academic_id": st.academic_id,
                "full_name": st.full_name,
                "branch_id": st.branch_id,
            } for st in students],
        })
    finally:
        s.close()


@doctor_bp.route("/api/doctor/me/attendance", methods=["GET"])
@require_role("doctor", "dean")
def my_attendance():
    user = get_current_user()
    if not user or not user.get("doctor_id"):
        return jsonify({"success": False, "error": "No doctor profile"}), 403
    course_id = request.args.get("course_id", type=int)
    s = get_session()
    try:
        course_ids = [c.id for c in s.query(Course).filter_by(doctor_id=user["doctor_id"]).all()]
        if course_id and course_id not in course_ids:
            return jsonify({"success": False, "error": "forbidden"}), 403
        query = s.query(AttendanceSession).filter(
            AttendanceSession.doctor_id == user["doctor_id"]
        )
        if course_id:
            query = query.filter_by(course_id=course_id)
        sessions = query.order_by(desc(AttendanceSession.start_timestamp)).limit(50).all()
        result = []
        for sess in sessions:
            records = s.query(AttendanceRecord).filter_by(session_id=sess.id).all()
            result.append({
                "session_id": sess.id,
                "course_id": sess.course_id,
                "date": sess.session_date.isoformat() if sess.session_date else "",
                "start": sess.start_timestamp.isoformat() if sess.start_timestamp else "",
                "is_active": sess.is_active,
                "attendance_count": len(records),
            })
        return jsonify({"success": True, "sessions": result})
    finally:
        s.close()


@doctor_bp.route("/api/doctor/me/notes", methods=["GET"])
@require_role("doctor", "dean")
def my_notes():
    user = get_current_user()
    if not user or not user.get("doctor_id"):
        return jsonify({"success": False, "error": "No doctor profile"}), 403
    s = get_session()
    try:
        notes = s.query(DoctorNote).filter_by(doctor_id=user["doctor_id"]).order_by(
            desc(DoctorNote.created_at)).all()
        return jsonify({
            "success": True,
            "notes": [{
                "id": n.id,
                "student_id": n.student_id,
                "student_name": n.student.full_name if n.student else "",
                "course_id": n.course_id,
                "course_name": n.course.course_name if n.course else "",
                "note": n.note,
                "severity": n.severity,
                "is_read": n.is_read_by_secretary,
                "created_at": n.created_at.isoformat() if n.created_at else "",
            } for n in notes],
        })
    finally:
        s.close()


@doctor_bp.route("/api/doctor/me/notes", methods=["POST"])
@require_role("doctor", "dean")
def add_note():
    user = get_current_user()
    if not user or not user.get("doctor_id"):
        return jsonify({"success": False, "error": "No doctor profile"}), 403
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400
    student_id = data.get("student_id")
    note_text = (data.get("note") or "").strip()
    if not student_id or not note_text:
        return jsonify({"success": False, "error": "student_id and note required"}), 400
    s = get_session()
    try:
        note = DoctorNote(
            doctor_id=user["doctor_id"],
            student_id=student_id,
            course_id=data.get("course_id"),
            note=note_text,
            severity=data.get("severity", "info"),
        )
        s.add(note)
        s.commit()
        return jsonify({"success": True, "id": note.id})
    except Exception as e:
        s.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        s.close()


@doctor_bp.route("/api/doctor/me/notes/<int:nid>", methods=["DELETE"])
@require_role("doctor", "dean")
def delete_note(nid):
    user = get_current_user()
    if not user or not user.get("doctor_id"):
        return jsonify({"success": False, "error": "No doctor profile"}), 403
    s = get_session()
    try:
        note = s.query(DoctorNote).filter_by(id=nid, doctor_id=user["doctor_id"]).first()
        if not note:
            return jsonify({"success": False, "error": "Not found"}), 404
        s.delete(note)
        s.commit()
        return jsonify({"success": True})
    except Exception as e:
        s.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        s.close()


@doctor_bp.route("/api/students/<int:student_id>/notes", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def student_notes(student_id):
    user = get_current_user()
    s = get_session()
    try:
        query = s.query(DoctorNote).filter_by(student_id=student_id)
        if user and user["role"] == "doctor":
            query = query.filter_by(doctor_id=user.get("doctor_id"))
        notes = query.order_by(desc(DoctorNote.created_at)).all()
        return jsonify({
            "success": True,
            "notes": [{
                "id": n.id,
                "doctor_id": n.doctor_id,
                "doctor_name": n.doctor.full_name if n.doctor else "",
                "course_name": n.course.course_name if n.course else "",
                "note": n.note,
                "severity": n.severity,
                "is_read": n.is_read_by_secretary,
                "created_at": n.created_at.isoformat() if n.created_at else "",
            } for n in notes],
        })
    finally:
        s.close()


@doctor_bp.route("/api/doctor-notes/<int:nid>/mark-read", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def mark_note_read(nid):
    s = get_session()
    try:
        note = s.query(DoctorNote).filter_by(id=nid).first()
        if not note:
            return jsonify({"success": False, "error": "Not found"}), 404
        note.is_read_by_secretary = True
        s.commit()
        return jsonify({"success": True})
    except Exception as e:
        s.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        s.close()


@doctor_bp.route("/api/doctor-notes/unread", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary")
def unread_notes():
    s = get_session()
    try:
        notes = s.query(DoctorNote).filter_by(is_read_by_secretary=False).order_by(
            desc(DoctorNote.created_at)).limit(200).all()
        return jsonify({
            "success": True,
            "notes": [{
                "id": n.id,
                "doctor_id": n.doctor_id,
                "doctor_name": n.doctor.full_name if n.doctor else "",
                "student_id": n.student_id,
                "student_name": n.student.full_name if n.student else "",
                "course_name": n.course.course_name if n.course else "",
                "note": n.note,
                "severity": n.severity,
                "created_at": n.created_at.isoformat() if n.created_at else "",
            } for n in notes],
            "count": len(notes),
        })
    finally:
        s.close()


# ════════════════════════ العلامات (Grades) ════════════════════════

def _compute_total(midterm, practical, final_exam, given_total):
    if given_total is not None:
        return given_total
    parts = [v for v in (midterm, practical, final_exam) if v is not None]
    return round(sum(parts), 2) if parts else None


@doctor_bp.route("/api/doctor/me/grades", methods=["GET"])
@require_role("doctor", "dean")
def doctor_get_grades():
    """دكتور المادة يرى علامات مادته مع كامل قائمة الطلاب المسجّلين."""
    user = get_current_user()
    if not user or not user.get("doctor_id"):
        return jsonify({"success": False, "error": "No doctor profile"}), 403
    try:
        course_id = int(request.args.get("course_id"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "course_id required"}), 400
    s = get_session()
    try:
        course = s.query(Course).filter_by(id=course_id).first()
        if not course:
            return jsonify({"success": False, "error": "course not found"}), 404
        if user["role"] != "dean" and course.doctor_id != user["doctor_id"]:
            return jsonify({"success": False, "error": "not your course"}), 403
        enrollments = s.query(Enrollment).filter_by(course_id=course_id).all()
        grades = {g.student_id: g for g in s.query(Grade).filter_by(course_id=course_id).all()}
        rows = []
        for e in enrollments:
            st = s.query(Student).filter_by(id=e.student_id).first()
            g = grades.get(e.student_id)
            rows.append({
                "student_id": e.student_id,
                "academic_id": st.academic_id if st else None,
                "full_name": st.full_name if st else None,
                "midterm": g.midterm if g else None,
                "practical": g.practical if g else None,
                "final_exam": g.final_exam if g else None,
                "total": g.total if g else None,
                "notes": g.notes if g else None,
            })
        rows.sort(key=lambda r: (r["full_name"] or ""))
        return jsonify({"success": True, "course_id": course_id,
                        "course_name": course.course_name,
                        "editable": True, "grades": rows})
    finally:
        s.close()


@doctor_bp.route("/api/doctor/me/grades", methods=["PUT"])
@require_role("doctor", "dean")
def doctor_put_grade():
    """دكتور المادة فقط يحرّر علامة طالب في مادته."""
    user = get_current_user()
    if not user or not user.get("doctor_id"):
        return jsonify({"success": False, "error": "No doctor profile"}), 403
    data = request.get_json() or {}
    try:
        course_id = int(data.get("course_id"))
        student_id = int(data.get("student_id"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "course_id and student_id required"}), 400

    def _num(key):
        v = data.get(key)
        if v in (None, ""):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    s = get_session()
    try:
        course = s.query(Course).filter_by(id=course_id).first()
        if not course:
            return jsonify({"success": False, "error": "course not found"}), 404
        if user["role"] != "dean" and course.doctor_id != user["doctor_id"]:
            return jsonify({"success": False, "error": "not your course"}), 403
        enr = s.query(Enrollment).filter_by(course_id=course_id, student_id=student_id).first()
        if not enr:
            return jsonify({"success": False, "error": "student not enrolled"}), 400
        midterm, practical, final_exam = _num("midterm"), _num("practical"), _num("final_exam")
        total = _compute_total(midterm, practical, final_exam, _num("total"))
        notes = (data.get("notes") or "").strip() or None

        g = s.query(Grade).filter_by(course_id=course_id, student_id=student_id).first()
        if g is None:
            g = Grade(course_id=course_id, student_id=student_id)
            s.add(g)
        g.midterm, g.practical, g.final_exam = midterm, practical, final_exam
        g.total, g.notes, g.updated_by = total, notes, user["id"]
        s.commit()
        return jsonify({"success": True, "total": total})
    except Exception as e:
        s.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        s.close()


@doctor_bp.route("/api/grades/overview", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary")
def grades_overview():
    """عرض العلامات للعميدة/النائب/السكرتارية — قراءة فقط، مع فلترة بالمادة/الدكتور."""
    course_id = request.args.get("course_id")
    doctor_id = request.args.get("doctor_id")
    s = get_session()
    try:
        cq = s.query(Course)
        if doctor_id:
            cq = cq.filter(Course.doctor_id == int(doctor_id))
        if course_id:
            cq = cq.filter(Course.id == int(course_id))
        courses = cq.all()
        out = []
        for c in courses:
            doc = s.query(Doctor).filter_by(id=c.doctor_id).first() if c.doctor_id else None
            grades = {g.student_id: g for g in s.query(Grade).filter_by(course_id=c.id).all()}
            enrollments = s.query(Enrollment).filter_by(course_id=c.id).all()
            for e in enrollments:
                st = s.query(Student).filter_by(id=e.student_id).first()
                g = grades.get(e.student_id)
                out.append({
                    "course_id": c.id,
                    "course_name": c.course_name,
                    "doctor_name": doc.full_name if doc else None,
                    "student_id": e.student_id,
                    "academic_id": st.academic_id if st else None,
                    "full_name": st.full_name if st else None,
                    "midterm": g.midterm if g else None,
                    "practical": g.practical if g else None,
                    "final_exam": g.final_exam if g else None,
                    "total": g.total if g else None,
                })
        out.sort(key=lambda r: (r["course_name"] or "", r["full_name"] or ""))
        return jsonify({"success": True, "editable": False, "rows": out})
    finally:
        s.close()
