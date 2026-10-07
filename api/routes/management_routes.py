from flask import Blueprint, request, jsonify
from database import get_session
from database.models import (
    Doctor, Course, Hall, Schedule, Enrollment,
    Student, User, Branch, Device, AttendanceSession, AttendanceRecord,
    ScanLog,
)
from security.security_manager import hash_rfid_uid, hash_password, generate_device_token
from datetime import datetime, time, timedelta, date as date_type
from pathlib import Path
from api.auth import require_role
from api.audit import log_action
from api.controllers.alert_controller import calculate_attendance_percentage
from sqlalchemy import or_, and_, func

mgmt_bp = Blueprint("management", __name__)


PLACEHOLDER_CARD_PREFIX = "__PLACEHOLDER__"


def _is_placeholder_card(hashed_uid):
    return bool(hashed_uid and str(hashed_uid).startswith(PLACEHOLDER_CARD_PREFIX))


def _card_hint(hashed_uid):
    if not hashed_uid or _is_placeholder_card(hashed_uid):
        return None
    return str(hashed_uid)[-4:]


def _placeholder_card_value(role, holder_id):
    return f"{PLACEHOLDER_CARD_PREFIX}{role}_reassigned_{holder_id}"


_LOG_DIR = Path(__file__).resolve().parents[2] / "data"
_DIAGNOSTICS_LOGS = {
    "app": "app.log",
    "errors": "errors.log",
    "scan": "scan_debug.log",
}


def _tail_text_file(path, max_lines):
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return "", False

    truncated = len(lines) > max_lines
    return "".join(lines[-max_lines:]), truncated


@mgmt_bp.route("/api/diagnostics/log", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary")
def get_diagnostics_log():
    log_type = (request.args.get("type") or "app").strip().lower()
    if log_type not in _DIAGNOSTICS_LOGS:
        return jsonify({"success": False, "error": "invalid log type"}), 400

    lines = request.args.get("lines", 500, type=int) or 500
    lines = max(1, min(lines, 5000))

    filename = _DIAGNOSTICS_LOGS[log_type]
    path = _LOG_DIR / filename
    content, truncated = _tail_text_file(path, lines)
    return jsonify({
        "success": True,
        "type": log_type,
        "filename": filename,
        "log_dir": str(_LOG_DIR),
        "content": content,
        "truncated": truncated,
        "exists": path.exists(),
    })


@mgmt_bp.route("/api/cards/lookup", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def lookup_card():
    uid = (request.args.get("uid") or "").strip()
    if not uid:
        return jsonify({"success": False, "error": "uid required"}), 400

    owner_type = (request.args.get("owner_type") or "").strip().lower()
    owner_id = request.args.get("owner_id", type=int)

    try:
        hashed_uid = hash_rfid_uid(uid)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

    session = get_session()
    try:
        doctor = session.query(Doctor).filter_by(hashed_uid=hashed_uid).first()
        if doctor:
            return jsonify({
                "success": True,
                "linked_to": "doctor",
                "id": doctor.id,
                "name": doctor.full_name,
                "is_self": owner_type == "doctor" and owner_id == doctor.id,
            })

        student = session.query(Student).filter_by(hashed_uid=hashed_uid).first()
        if student:
            return jsonify({
                "success": True,
                "linked_to": "student",
                "id": student.id,
                "name": student.full_name,
                "is_self": owner_type == "student" and owner_id == student.id,
            })

        return jsonify({"success": True, "linked_to": None})
    finally:
        session.close()


@mgmt_bp.route("/api/doctors", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_doctors():
    session = get_session()
    try:
        doctors = session.query(Doctor).all()
        result = []
        for d in doctors:
            user = session.query(User).filter_by(id=d.user_id).first() if d.user_id else None
            result.append({
                "id": d.id,
                "full_name": d.full_name,
                "first_name": d.first_name,
                "last_name": d.last_name,
                "hashed_uid": d.hashed_uid,
                "is_placeholder_card": _is_placeholder_card(d.hashed_uid),
                "card_hint": _card_hint(d.hashed_uid),
                "user_id": d.user_id,
                "username": user.username if user else None,
                "courses": [{"id": c.id, "course_name": c.course_name, "course_code": c.course_code}
                            for c in d.courses],
            })
        return jsonify({"success": True, "doctors": result})
    finally:
        session.close()


@mgmt_bp.route("/api/doctors/<int:doctor_id>", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_doctor(doctor_id):
    session = get_session()
    try:
        d = session.query(Doctor).filter_by(id=doctor_id).first()
        if not d:
            return jsonify({"success": False, "error": "Doctor not found"}), 404
        user = session.query(User).filter_by(id=d.user_id).first() if d.user_id else None
        return jsonify({"success": True, "doctor": {
            "id": d.id,
            "full_name": d.full_name,
            "first_name": d.first_name,
            "last_name": d.last_name,
            "hashed_uid": d.hashed_uid,
            "is_placeholder_card": _is_placeholder_card(d.hashed_uid),
            "card_hint": _card_hint(d.hashed_uid),
            "user_id": d.user_id,
            "username": user.username if user else None,
            "courses_count": len(d.courses),
        }})
    finally:
        session.close()


@mgmt_bp.route("/api/doctors", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def add_doctor():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    first_name = str(data.get("first_name", "")).strip()
    last_name = str(data.get("last_name", "")).strip()
    full_name = str(data.get("full_name", "")).strip()
    if not full_name and (first_name or last_name):
        full_name = " ".join(p for p in [first_name, last_name] if p)
    uid = str(data.get("uid", "")).strip()
    create_user = data.get("create_user", False)
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()
    doctor_type = str(data.get("doctor_type", "theory")).strip()
    role = str(data.get("role", "doctor")).strip()

    if not full_name:
        return jsonify({"success": False, "error": "الاسم الكامل مطلوب"}), 400
    if not uid:
        return jsonify({"success": False, "error": "UID البطاقة مطلوب"}), 400

    session = get_session()
    try:
        existing_name = session.query(Doctor).filter(
            Doctor.full_name.ilike(full_name)).first()
        if existing_name:
            return jsonify({"success": False,
                             "error": f"يوجد دكتور بنفس الاسم: {full_name}"}), 400

        hashed = hash_rfid_uid(uid)

        existing = session.query(Doctor).filter_by(hashed_uid=hashed).first()
        if existing:
            return jsonify({"success": False,
                             "error": f"هذه البطاقة مستخدمة من قبل الدكتور: {existing.full_name}"}), 400

        existing_student = session.query(Student).filter_by(hashed_uid=hashed).first()
        if existing_student:
            return jsonify({"success": False,
                             "error": f"هذه البطاقة مستخدمة من قبل الطالب: {existing_student.full_name}"}), 400

        user_id = None
        if create_user and username and password:
            existing_user = session.query(User).filter_by(username=username).first()
            if existing_user:
                return jsonify({"success": False,
                                 "error": f"اسم المستخدم '{username}' محجوز"}), 400
            user_role = role if role in ("doctor", "dean") else "doctor"
            new_user = User(
                username=username,
                password_hash=hash_password(password),
                role=user_role,
            )
            session.add(new_user)
            session.flush()
            user_id = new_user.id

        doctor = Doctor(
            full_name=full_name,
            first_name=first_name or None,
            last_name=last_name or None,
            hashed_uid=hashed,
            user_id=user_id,
        )
        session.add(doctor)
        session.commit()
        session.refresh(doctor)
        log_action("create", "doctor", doctor.id, doctor.full_name)

        return jsonify({
            "success": True,
            "message": "تمت إضافة الدكتور بنجاح",
            "doctor_id": doctor.id,
            "user_created": create_user and user_id is not None,
        })

    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/doctors/<int:doctor_id>", methods=["PUT"])
@require_role("dean", "dean_assistant", "secretary")
def update_doctor(doctor_id):
    data = request.get_json() or {}
    session = get_session()
    try:
        doctor = session.query(Doctor).filter_by(id=doctor_id).first()
        if not doctor:
            return jsonify({"success": False, "error": "Doctor not found"}), 404

        if "full_name" in data and data["full_name"].strip():
            new_name = data["full_name"].strip()
            other = session.query(Doctor).filter(
                Doctor.full_name.ilike(new_name),
                Doctor.id != doctor_id).first()
            if other:
                return jsonify({"success": False,
                                 "error": f"يوجد دكتور آخر بنفس الاسم: {new_name}"}), 400
            doctor.full_name = new_name

        for fld in ("first_name", "last_name"):
            if fld in data:
                setattr(doctor, fld, (data[fld] or "").strip() or None)

        if "uid" in data and data["uid"].strip():
            new_uid = data["uid"].strip()
            new_hash = hash_rfid_uid(new_uid)
            force_uid_change = bool(data.get("force_uid_change"))

            if new_hash == doctor.hashed_uid:
                return jsonify({"success": False,
                                 "error": "البطاقة المُدخلة هي نفس البطاقة الحالية للدكتور"}), 400

            existing = session.query(Doctor).filter(
                Doctor.hashed_uid == new_hash,
                Doctor.id != doctor_id).first()
            if existing:
                if force_uid_change:
                    existing.hashed_uid = _placeholder_card_value("doctor", existing.id)
                    session.flush()
                else:
                    return jsonify({"success": False,
                                     "error": f"هذه البطاقة مستخدمة من قبل الدكتور: {existing.full_name}"}), 400

            existing_student = session.query(Student).filter_by(hashed_uid=new_hash).first()
            if existing_student:
                return jsonify({"success": False,
                                 "error": f"هذه البطاقة مستخدمة من قبل الطالب: {existing_student.full_name}"}), 400

            doctor.hashed_uid = new_hash

        if data.get("create_user"):
            username = str(data.get("username", "")).strip()
            password = str(data.get("password", "")).strip()
            new_role = str(data.get("role", "doctor")).strip()
            if username and password:
                if doctor.user_id:
                    return jsonify({"success": False,
                                     "error": "هذا الدكتور لديه حساب مسبقاً"}), 400
                if session.query(User).filter_by(username=username).first():
                    return jsonify({"success": False,
                                     "error": f"اسم المستخدم محجوز: {username}"}), 400
                new_user = User(
                    username=username,
                    password_hash=hash_password(password),
                    role=new_role if new_role in ("doctor", "dean") else "doctor",
                )
                session.add(new_user)
                session.flush()
                doctor.user_id = new_user.id

        session.commit()
        log_action("update", "doctor", doctor_id, doctor.full_name)
        return jsonify({"success": True, "message": "تم تحديث بيانات الدكتور"})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/doctors/<int:doctor_id>", methods=["DELETE"])
@require_role("dean", "dean_assistant", "secretary")
def delete_doctor(doctor_id):
    session = get_session()
    try:
        doctor = session.query(Doctor).filter_by(id=doctor_id).first()
        if not doctor:
            return jsonify({"success": False, "error": "Doctor not found"}), 404

        courses = session.query(Course).filter_by(doctor_id=doctor_id).all()
        for c in courses:
            c.doctor_id = None

        from database.models import AttendanceSession
        sessions = session.query(AttendanceSession).filter_by(
            doctor_id=doctor_id).all()
        for s in sessions:
            session.delete(s)

        user_id = doctor.user_id
        name = doctor.full_name
        session.delete(doctor)

        if user_id:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                session.delete(user)

        session.commit()
        log_action("delete", "doctor", doctor_id, name)
        return jsonify({"success": True, "message": "تم حذف الدكتور بنجاح"})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/courses/full", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_courses_full():
    session = get_session()
    try:
        courses = session.query(Course).all()
        result = []
        for c in courses:
            doctor = session.query(Doctor).filter_by(id=c.doctor_id).first() if c.doctor_id else None
            branch = session.query(Branch).filter_by(id=c.branch_id).first() if c.branch_id else None
            result.append({
                "id": c.id,
                "course_code": c.course_code,
                "course_name": c.course_name,
                "course_type": c.course_type,
                "total_weeks": c.total_weeks,
                "doctor_id": c.doctor_id,
                "doctor_name": doctor.full_name if doctor else "—",
                "branch_id": c.branch_id,
                "branch_name": branch.branch_name if branch else "—",
                "enrolled_count": session.query(Enrollment).filter_by(course_id=c.id).count(),
            })
        return jsonify({"success": True, "courses": result})
    finally:
        session.close()


@mgmt_bp.route("/api/courses", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def add_course():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400

    course_code = str(data.get("course_code", "")).strip().upper()
    course_name = str(data.get("course_name", "")).strip()
    course_type = str(data.get("course_type", "theory")).strip()
    total_weeks = int(data.get("total_weeks", 15) or 15)
    doctor_id = data.get("doctor_id")
    branch_id = data.get("branch_id")

    if not course_code or not course_name:
        return jsonify({"success": False, "error": "Course code and name are required"}), 400

    session = get_session()
    try:
        if session.query(Course).filter_by(course_code=course_code).first():
            return jsonify({"success": False, "error": f"Course code '{course_code}' already exists"}), 400

        course = Course(
            course_code=course_code,
            course_name=course_name,
            course_type=course_type,
            total_weeks=total_weeks,
            doctor_id=doctor_id if doctor_id else None,
            branch_id=branch_id if branch_id else None,
        )
        session.add(course)
        session.commit()
        log_action("create", "course", course.id, course.course_name)
        session.refresh(course)
        return jsonify({"success": True, "message": "Course added", "course_id": course.id})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/courses/<int:course_id>", methods=["PUT"])
@require_role("dean", "dean_assistant", "secretary")
def update_course(course_id):
    data = request.get_json()
    session = get_session()
    try:
        course = session.query(Course).filter_by(id=course_id).first()
        if not course:
            return jsonify({"success": False, "error": "Course not found"}), 404

        if "course_name" in data:
            course.course_name = data["course_name"].strip()
        if "course_type" in data:
            course.course_type = data["course_type"]
        if "total_weeks" in data:
            course.total_weeks = int(data["total_weeks"])
        if "doctor_id" in data:
            course.doctor_id = data["doctor_id"] or None
        if "branch_id" in data:
            course.branch_id = data["branch_id"] or None

        session.commit()
        log_action("update", "course", course_id, course.course_name)
        return jsonify({"success": True, "message": "Course updated"})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/courses/<int:course_id>", methods=["DELETE"])
@require_role("dean", "dean_assistant", "secretary")
def delete_course(course_id):
    session = get_session()
    try:
        course = session.query(Course).filter_by(id=course_id).first()
        if not course:
            return jsonify({"success": False, "error": "Course not found"}), 404
        name = course.course_name
        session.delete(course)
        session.commit()
        log_action("delete", "course", course_id, name)
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/halls", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_halls():
    session = get_session()
    try:
        halls = session.query(Hall).all()
        return jsonify({
            "success": True,
            "halls": [{"id": h.id, "hall_name": h.hall_name, "hall_type": h.hall_type} for h in halls],
        })
    finally:
        session.close()


@mgmt_bp.route("/api/halls", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def add_hall():
    data = request.get_json()
    hall_name = str(data.get("hall_name", "")).strip()
    hall_type = str(data.get("hall_type", "theory")).strip()

    if not hall_name:
        return jsonify({"success": False, "error": "Hall name required"}), 400

    session = get_session()
    try:
        if session.query(Hall).filter_by(hall_name=hall_name).first():
            return jsonify({"success": False, "error": "Hall already exists"}), 400
        hall = Hall(hall_name=hall_name, hall_type=hall_type)
        session.add(hall)
        session.commit()
        session.refresh(hall)
        log_action("create", "hall", hall.id, hall.hall_name)
        return jsonify({"success": True, "hall_id": hall.id})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/halls/<int:hall_id>", methods=["DELETE"])
@require_role("dean", "dean_assistant", "secretary")
def delete_hall(hall_id):
    session = get_session()
    try:
        hall = session.query(Hall).filter_by(id=hall_id).first()
        if not hall:
            return jsonify({"success": False, "error": "Hall not found"}), 404
        name = hall.hall_name
        session.delete(hall)
        session.commit()
        log_action("delete", "hall", hall_id, name)
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@mgmt_bp.route("/api/schedules", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_schedules():
    course_id = request.args.get("course_id", type=int)
    session = get_session()
    try:
        q = session.query(Schedule)
        if course_id:
            q = q.filter_by(course_id=course_id)
        schedules = q.all()
        result = []
        for s in schedules:
            course = session.query(Course).filter_by(id=s.course_id).first()
            hall = session.query(Hall).filter_by(id=s.hall_id).first()
            result.append({
                "id": s.id,
                "course_id": s.course_id,
                "course_name": course.course_name if course else "?",
                "course_code": course.course_code if course else "?",
                "hall_id": s.hall_id,
                "hall_name": hall.hall_name if hall else "?",
                "day_of_week": s.day_of_week,
                "day_name": DAYS[s.day_of_week] if 0 <= s.day_of_week <= 6 else "?",
                "start_time": str(s.start_time),
                "end_time": str(s.end_time),
            })
        return jsonify({"success": True, "schedules": result})
    finally:
        session.close()


@mgmt_bp.route("/api/schedules", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def add_schedule():
    data = request.get_json()
    course_id = data.get("course_id")
    hall_id = data.get("hall_id")
    day = data.get("day_of_week")
    start = data.get("start_time")
    end = data.get("end_time")

    if not all([course_id, hall_id, day is not None, start, end]):
        return jsonify({"success": False, "error": "All fields required"}), 400

    session = get_session()
    try:
        start_t = datetime.strptime(start, "%H:%M").time()
        end_t = datetime.strptime(end, "%H:%M").time()

        conflict = _find_schedule_conflict(
            session, int(hall_id), int(day), start_t, end_t
        )
        if conflict:
            return jsonify({
                "success": False,
                "error": "conflict",
                "message": "تعارض زمني مع جدول آخر في نفس القاعة",
                "conflict_schedule_id": conflict.id,
            }), 409

        sched = Schedule(
            course_id=course_id,
            hall_id=hall_id,
            day_of_week=int(day),
            start_time=start_t,
            end_time=end_t,
        )
        session.add(sched)
        session.commit()
        session.refresh(sched)
        log_action("create", "schedule", sched.id, f"course:{sched.course_id}")
        return jsonify({"success": True, "schedule_id": sched.id})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/schedules/<int:sched_id>", methods=["DELETE"])
@require_role("dean", "dean_assistant", "secretary")
def delete_schedule(sched_id):
    session = get_session()
    try:
        s = session.query(Schedule).filter_by(id=sched_id).first()
        if not s:
            return jsonify({"success": False, "error": "Schedule not found"}), 404
        saved_course_id = s.course_id
        session.delete(s)
        session.commit()
        log_action("delete", "schedule", sched_id, f"course:{saved_course_id}")
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/schedules/<int:sched_id>", methods=["PUT"])
@require_role("dean", "dean_assistant", "secretary")
def update_schedule(sched_id):
    data = request.get_json() or {}
    session = get_session()
    try:
        s = session.query(Schedule).filter_by(id=sched_id).first()
        if not s:
            return jsonify({"success": False, "error": "Schedule not found"}), 404

        if "course_id" in data and data["course_id"]:
            s.course_id = int(data["course_id"])
        if "hall_id" in data and data["hall_id"]:
            s.hall_id = int(data["hall_id"])
        if "day_of_week" in data and data["day_of_week"] is not None:
            s.day_of_week = int(data["day_of_week"])
        if "start_time" in data and data["start_time"]:
            s.start_time = datetime.strptime(data["start_time"], "%H:%M").time()
        if "end_time" in data and data["end_time"]:
            s.end_time = datetime.strptime(data["end_time"], "%H:%M").time()

        conflict = _find_schedule_conflict(
            session, s.hall_id, s.day_of_week, s.start_time, s.end_time, exclude_id=s.id
        )
        if conflict:
            return jsonify({
                "success": False,
                "error": "conflict",
                "message": "تعارض زمني مع جدول آخر في نفس القاعة",
                "conflict_schedule_id": conflict.id,
            }), 409

        session.commit()
        log_action("update", "schedule", sched_id, f"course:{s.course_id}")
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


def _find_schedule_conflict(session, hall_id, day_of_week, start_t, end_t, exclude_id=None):
    q = session.query(Schedule).filter(
        Schedule.hall_id == hall_id,
        Schedule.day_of_week == day_of_week,
        Schedule.start_time < end_t,
        Schedule.end_time > start_t,
    )
    if exclude_id is not None:
        q = q.filter(Schedule.id != exclude_id)
    return q.first()


@mgmt_bp.route("/api/schedules/conflicts", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def check_schedule_conflict():
    data = request.get_json() or {}
    try:
        hall_id = int(data["hall_id"])
        day = int(data["day_of_week"])
        start_t = datetime.strptime(data["start_time"], "%H:%M").time()
        end_t = datetime.strptime(data["end_time"], "%H:%M").time()
    except (KeyError, ValueError) as e:
        return jsonify({"success": False, "error": f"bad params: {e}"}), 400

    exclude_id = data.get("exclude_id")
    session = get_session()
    try:
        conflict = _find_schedule_conflict(session, hall_id, day, start_t, end_t, exclude_id=exclude_id)
        if not conflict:
            return jsonify({"success": True, "has_conflict": False})
        course = session.query(Course).filter_by(id=conflict.course_id).first()
        return jsonify({
            "success": True,
            "has_conflict": True,
            "conflict": {
                "id": conflict.id,
                "course_name": course.course_name if course else "?",
                "course_code": course.course_code if course else "?",
                "start_time": str(conflict.start_time),
                "end_time": str(conflict.end_time),
            },
        })
    finally:
        session.close()


@mgmt_bp.route("/api/enrollments", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_enrollments():
    course_id = request.args.get("course_id", type=int)
    student_id = request.args.get("student_id", type=int)
    session = get_session()
    try:
        q = session.query(Enrollment)
        if course_id:
            q = q.filter_by(course_id=course_id)
        if student_id:
            q = q.filter_by(student_id=student_id)
        enrollments = q.all()
        result = []
        for e in enrollments:
            student = session.query(Student).filter_by(id=e.student_id).first()
            course = session.query(Course).filter_by(id=e.course_id).first()
            result.append({
                "id": e.id,
                "student_id": e.student_id,
                "academic_id": student.academic_id if student else "?",
                "student_name": student.full_name if student else "?",
                "course_id": e.course_id,
                "course_name": course.course_name if course else "?",
                "course_code": course.course_code if course else "?",
                "enrollment_date": str(e.enrollment_date),
            })
        return jsonify({"success": True, "enrollments": result})
    finally:
        session.close()


@mgmt_bp.route("/api/enrollments", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def add_enrollment():
    data = request.get_json()
    student_id = data.get("student_id")
    course_id = data.get("course_id")

    if not student_id or not course_id:
        return jsonify({"success": False, "error": "student_id and course_id required"}), 400

    session = get_session()
    try:
        exists = session.query(Enrollment).filter_by(
            student_id=student_id, course_id=course_id
        ).first()
        if exists:
            return jsonify({"success": False, "error": "Student already enrolled in this course"}), 400

        e = Enrollment(student_id=student_id, course_id=course_id)
        session.add(e)
        session.commit()
        log_action("create", "enrollment", e.id, f"student:{student_id} course:{course_id}")
        return jsonify({"success": True, "message": "Enrolled successfully"})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/enrollments/<int:enrollment_id>", methods=["DELETE"])
@require_role("dean", "dean_assistant", "secretary")
def delete_enrollment(enrollment_id):
    session = get_session()
    try:
        e = session.query(Enrollment).filter_by(id=enrollment_id).first()
        if not e:
            return jsonify({"success": False, "error": "Enrollment not found"}), 404
        saved_student_id = e.student_id
        saved_course_id = e.course_id
        session.delete(e)
        session.commit()
        log_action("delete", "enrollment", enrollment_id, f"student:{saved_student_id} course:{saved_course_id}")
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/devices", methods=["GET"])
def get_devices():
    """قائمة الأجهزة المسجَّلة.
    بدون auth: تستخدمها الـ ESP scanners لجلب توكنها (bootstrap).
    آمنة لأن:
      - النظام يعمل على LAN فقط.
      - الـ device_token يُستخدم لمصادقة الأجهزة لا المستخدمين.
      - أي مهاجم على نفس الشبكة يستطيع التقاط التوكن من حركة HTTP أصلاً.
    """
    session = get_session()
    try:
        devices = session.query(Device).all()
        result = []
        for d in devices:
            hall = session.query(Hall).filter_by(id=d.hall_id).first() if d.hall_id else None
            result.append({
                "id": d.id,
                "device_id": d.device_id,
                "hall_id": d.hall_id,
                "hall_name": hall.hall_name if hall else "—",
                "device_token": d.device_token,
                "is_active": d.is_active,
                "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            })
        return jsonify({"success": True, "devices": result})
    finally:
        session.close()


@mgmt_bp.route("/api/devices", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def add_device():
    data = request.get_json()
    device_id = str(data.get("device_id", "")).strip().upper()
    hall_id = data.get("hall_id")

    if not device_id:
        return jsonify({"success": False, "error": "Device ID required"}), 400

    session = get_session()
    try:
        if session.query(Device).filter_by(device_id=device_id).first():
            return jsonify({"success": False, "error": "Device ID already exists"}), 400
        token = generate_device_token()
        d = Device(device_id=device_id, hall_id=hall_id or None, device_token=token, is_active=True)
        session.add(d)
        session.commit()
        log_action("create", "device", d.id, d.device_id)
        return jsonify({"success": True, "device_token": token, "message": "Device registered"})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/students/<int:student_id>/stats", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def student_stats(student_id):
    session = get_session()
    try:
        enrollments = session.query(Enrollment).filter_by(student_id=student_id).all()
        result = []
        for enr in enrollments:
            course = session.query(Course).filter_by(id=enr.course_id).first()
            if not course:
                continue
            total_sessions = session.query(AttendanceSession).filter(
                AttendanceSession.course_id == course.id,
                AttendanceSession.is_active == False,
            ).count()
            attended = session.query(AttendanceRecord).join(
                AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id
            ).filter(
                AttendanceRecord.student_id == student_id,
                AttendanceSession.course_id == course.id,
                AttendanceRecord.status == "present",
            ).count()
            absent = session.query(AttendanceRecord).join(
                AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id
            ).filter(
                AttendanceRecord.student_id == student_id,
                AttendanceSession.course_id == course.id,
                AttendanceRecord.status == "absent",
            ).count()
            pct = round((attended / total_sessions * 100), 1) if total_sessions > 0 else 100.0
            result.append({
                "course_id": course.id,
                "course_code": course.course_code,
                "course_name": course.course_name,
                "total_sessions": total_sessions,
                "attended": attended,
                "absent": absent,
                "percentage": pct,
            })
        return jsonify({"success": True, "stats": result})
    finally:
        session.close()


@mgmt_bp.route("/api/enrollments/bulk", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def bulk_enroll():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400
    student_id = data.get("student_id")
    course_ids = data.get("course_ids", [])
    if not student_id or not course_ids:
        return jsonify({"success": False, "error": "student_id and course_ids required"}), 400

    session = get_session()
    try:
        created, skipped, conflicts = 0, 0, []
        for cid in course_ids:
            exists = session.query(Enrollment).filter_by(
                student_id=student_id, course_id=cid
            ).first()
            if exists:
                skipped += 1
                continue
            session.add(Enrollment(student_id=student_id, course_id=cid))
            created += 1
        session.commit()
        log_action("create", "enrollment", None, f"bulk student:{student_id} courses:{len(course_ids)} created:{created}")
        return jsonify({
            "success": True, "created": created,
            "skipped": skipped, "conflicts": conflicts,
        })
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/enrollments/check-conflict", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def check_conflict():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400
    student_id = data.get("student_id")
    course_id = data.get("course_id")
    if not student_id or not course_id:
        return jsonify({"success": False, "error": "student_id and course_id required"}), 400

    session = get_session()
    try:
        new_schedules = session.query(Schedule).filter_by(course_id=course_id).all()
        conflicts = []
        for ns in new_schedules:
            enrolled_courses = session.query(Enrollment).filter_by(
                student_id=student_id
            ).all()
            for ec in enrolled_courses:
                existing = session.query(Schedule).filter(
                    Schedule.course_id == ec.course_id,
                    Schedule.day_of_week == ns.day_of_week,
                    Schedule.start_time < ns.end_time,
                    Schedule.end_time > ns.start_time,
                ).first()
                if existing:
                    c = session.query(Course).filter_by(id=ec.course_id).first()
                    conflicts.append({
                        "existing_course": c.course_name if c else "?",
                        "day": ns.day_of_week,
                        "new_time": f"{ns.start_time}-{ns.end_time}",
                    })
        return jsonify({"success": True, "conflicts": conflicts})
    finally:
        session.close()


@mgmt_bp.route("/api/timetable", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_timetable():
    hall_id = request.args.get("hall_id", type=int)
    doctor_id = request.args.get("doctor_id", type=int)
    branch_id = request.args.get("branch_id", type=int)
    day_of_week = request.args.get("day_of_week", type=int)

    session = get_session()
    try:
        q = session.query(Schedule).join(Course).join(Hall)
        if hall_id:
            q = q.filter(Schedule.hall_id == hall_id)
        if doctor_id:
            q = q.filter(Course.doctor_id == doctor_id)
        if branch_id:
            q = q.filter(Course.branch_id == branch_id)
        if day_of_week is not None:
            q = q.filter(Schedule.day_of_week == day_of_week)

        schedules = q.all()
        result = []
        for s in schedules:
            course = session.query(Course).filter_by(id=s.course_id).first()
            doctor = session.query(Doctor).filter_by(id=course.doctor_id).first() if course and course.doctor_id else None
            hall = session.query(Hall).filter_by(id=s.hall_id).first()
            result.append({
                "id": s.id,
                "course_id": s.course_id,
                "course_code": course.course_code if course else "",
                "course_name": course.course_name if course else "",
                "doctor_name": doctor.full_name if doctor else "—",
                "hall_id": s.hall_id,
                "hall_name": hall.hall_name if hall else "",
                "day_of_week": s.day_of_week,
                "start_time": str(s.start_time),
                "end_time": str(s.end_time),
                "branch_id": course.branch_id if course else None,
            })
        return jsonify({"success": True, "timetable": result})
    finally:
        session.close()


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


@mgmt_bp.route("/api/scan-logs", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_scan_logs():
    args = request.args
    date_from = _parse_date(args.get("from"))
    date_to = _parse_date(args.get("to"))
    hall_id = args.get("hall_id", type=int)
    student_id = args.get("student_id", type=int)
    doctor_id = args.get("doctor_id", type=int)
    scan_type = args.get("scan_type")
    success_filter = args.get("success")
    search = (args.get("q") or "").strip()
    page = max(1, args.get("page", 1, type=int))
    per_page = min(200, max(10, args.get("per_page", 50, type=int)))

    session = get_session()
    try:
        q = session.query(ScanLog)
        if date_from:
            q = q.filter(ScanLog.timestamp >= datetime.combine(date_from, time.min))
        if date_to:
            q = q.filter(ScanLog.timestamp < datetime.combine(date_to + timedelta(days=1), time.min))
        if hall_id:
            q = q.filter(ScanLog.hall_id == hall_id)
        if student_id:
            q = q.filter(ScanLog.student_id == student_id)
        if doctor_id:
            q = q.filter(ScanLog.doctor_id == doctor_id)
        if scan_type and scan_type != "all":
            q = q.filter(ScanLog.scan_type == scan_type)
        if success_filter == "true":
            q = q.filter(ScanLog.success == True)
        elif success_filter == "false":
            q = q.filter(ScanLog.success == False)
        if search:
            like = f"%{search}%"
            q_with_names = q.outerjoin(Student, ScanLog.student_id == Student.id) \
                            .outerjoin(Doctor, ScanLog.doctor_id == Doctor.id) \
                            .filter(or_(
                                Student.full_name.ilike(like),
                                Student.academic_id.ilike(like),
                                Doctor.full_name.ilike(like),
                                ScanLog.raw_uid_hint.ilike(like),
                            ))
            q = q_with_names

        total = q.count()
        q = q.order_by(ScanLog.timestamp.desc())
        logs = q.offset((page - 1) * per_page).limit(per_page).all()

        result = []
        for lg in logs:
            student = lg.student
            doctor = lg.doctor
            hall = lg.hall
            result.append({
                "id": lg.id,
                "timestamp": lg.timestamp.isoformat() if lg.timestamp else None,
                "scan_type": lg.scan_type,
                "success": bool(lg.success),
                "hall_id": lg.hall_id,
                "hall_name": hall.hall_name if hall else None,
                "device_id": lg.device_id,
                "student_id": lg.student_id,
                "student_name": student.full_name if student else None,
                "academic_id": student.academic_id if student else None,
                "doctor_id": lg.doctor_id,
                "doctor_name": doctor.full_name if doctor else None,
                "session_id": lg.session_id,
                "raw_uid_hint": lg.raw_uid_hint,
                "error_reason": lg.error_reason,
            })
        return jsonify({
            "success": True,
            "logs": result,
            "page": page,
            "per_page": per_page,
            "total": total,
            "has_more": page * per_page < total,
        })
    finally:
        session.close()


@mgmt_bp.route("/api/scan-logs", methods=["DELETE"])
@require_role("dean", "dean_assistant")
def delete_scan_logs():
    """مسح سجلات الحضور — كل السجلات أو نطاق تاريخي.
    body اختياري: {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"} — إذا غير موجود يمسح الكل.
    """
    body = request.get_json(silent=True) or {}
    date_from = _parse_date(body.get("from")) if body.get("from") else None
    date_to = _parse_date(body.get("to")) if body.get("to") else None

    session = get_session()
    try:
        q = session.query(ScanLog)
        scope = "all"
        if date_from:
            q = q.filter(ScanLog.timestamp >= datetime.combine(date_from, time.min))
            scope = f"from={date_from}"
        if date_to:
            q = q.filter(ScanLog.timestamp < datetime.combine(date_to + timedelta(days=1), time.min))
            scope = scope + f",to={date_to}" if date_from else f"to={date_to}"
        deleted = q.delete(synchronize_session=False)
        session.commit()
        log_action("delete", "scan_logs", None, f"cleared {deleted} log(s) [{scope}]")
        return jsonify({"success": True, "deleted": deleted, "scope": scope})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@mgmt_bp.route("/api/scan-logs/halls-today", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_halls_today_summary():
    from utils.time_provider import today as tp_today
    today = tp_today()
    start_dt = datetime.combine(today, time.min)
    end_dt = datetime.combine(today + timedelta(days=1), time.min)
    session = get_session()
    try:
        halls = session.query(Hall).all()
        result = []
        for h in halls:
            base = session.query(ScanLog).filter(
                ScanLog.hall_id == h.id,
                ScanLog.timestamp >= start_dt,
                ScanLog.timestamp < end_dt,
            )
            success_count = base.filter(ScanLog.success == True).count()
            failure_count = base.filter(ScanLog.success == False).count()
            last = base.order_by(ScanLog.timestamp.desc()).first()
            result.append({
                "hall_id": h.id,
                "hall_name": h.hall_name,
                "success": success_count,
                "failure": failure_count,
                "last_scan": last.timestamp.isoformat() if last and last.timestamp else None,
                "last_scan_type": last.scan_type if last else None,
            })
        return jsonify({"success": True, "halls": result, "today": today.isoformat()})
    finally:
        session.close()


@mgmt_bp.route("/api/students/<int:student_id>/courses-detailed", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_student_courses_detailed(student_id):
    session = get_session()
    try:
        student = session.query(Student).filter_by(id=student_id).first()
        if not student:
            return jsonify({"success": False, "error": "Student not found"}), 404

        enrollments = session.query(Enrollment).filter_by(student_id=student_id).all()
        result = []
        total_weekly_minutes = 0
        for e in enrollments:
            course = session.query(Course).filter_by(id=e.course_id).first()
            if not course:
                continue
            doctor = session.query(Doctor).filter_by(id=course.doctor_id).first() if course.doctor_id else None
            schedules = session.query(Schedule).filter_by(course_id=course.id).all()
            sched_list = []
            for s in schedules:
                hall = session.query(Hall).filter_by(id=s.hall_id).first()
                if s.start_time and s.end_time:
                    sm = s.start_time.hour * 60 + s.start_time.minute
                    em = s.end_time.hour * 60 + s.end_time.minute
                    total_weekly_minutes += max(0, em - sm)
                sched_list.append({
                    "id": s.id,
                    "day_of_week": s.day_of_week,
                    "start_time": str(s.start_time),
                    "end_time": str(s.end_time),
                    "hall_name": hall.hall_name if hall else None,
                })
            result.append({
                "enrollment_id": e.id,
                "course_id": course.id,
                "course_code": course.course_code,
                "course_name": course.course_name,
                "course_type": course.course_type,
                "doctor_name": doctor.full_name if doctor else None,
                "schedules": sched_list,
            })
        return jsonify({
            "success": True,
            "courses": result,
            "total_courses": len(result),
            "total_weekly_hours": round(total_weekly_minutes / 60.0, 2),
        })
    finally:
        session.close()
