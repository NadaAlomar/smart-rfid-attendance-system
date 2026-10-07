from flask import Blueprint, request, jsonify, send_file
from database import get_session
from database.models import (
    Student, Course, Enrollment, Doctor, User,
    Branch, Hall, Device, AttendanceSession, AttendanceRecord, Setting,
)
from security.security_manager import hash_password, hash_rfid_uid, generate_device_token
from api.auth import require_role
from api.audit import log_action
from api.controllers.alert_controller import (
    get_active_alerts, mark_alert_as_read, generate_weekly_report,
    calculate_attendance_percentage,
)
from utils.excel_handler import (
    import_students, import_courses, import_full_data,
    export_attendance_report, generate_sample_excel_template,
)
from datetime import datetime
import config
import os
import shutil
import glob as glob_mod

secretary_bp = Blueprint("secretary", __name__)


PLACEHOLDER_CARD_PREFIX = "__PLACEHOLDER__"


def _is_placeholder_card(hashed_uid):
    return bool(hashed_uid and str(hashed_uid).startswith(PLACEHOLDER_CARD_PREFIX))


def _card_hint(hashed_uid):
    if not hashed_uid or _is_placeholder_card(hashed_uid):
        return None
    return str(hashed_uid)[-4:]


def _placeholder_card_value(role, holder_id):
    return f"{PLACEHOLDER_CARD_PREFIX}{role}_reassigned_{holder_id}"


# ── Branches ──────────────────────────────────────────────────────────────────
@secretary_bp.route("/api/branches", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_branches():
    session = get_session()
    try:
        branches = session.query(Branch).all()
        return jsonify({
            "success": True,
            "branches": [{"id": b.id, "branch_name": b.branch_name, "branch_code": b.branch_code} for b in branches],
        })
    finally:
        session.close()


# ── Manual Attendance ────────────────────────────────────────────────────────
@secretary_bp.route("/api/attendance/manual", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def add_manual_attendance():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400
    session_id = data.get("session_id")
    student_id = data.get("student_id")
    status = data.get("status", "present")
    if not session_id or not student_id:
        return jsonify({"success": False, "error": "session_id and student_id required"}), 400

    db = get_session()
    try:
        enrollment = db.query(Enrollment).filter_by(
            student_id=student_id,
            course_id=db.query(AttendanceSession).filter_by(id=session_id).first().course_id
        ).first() if db.query(AttendanceSession).filter_by(id=session_id).first() else None
        if not enrollment:
            return jsonify({"success": False, "error": "Student not enrolled in this course"}), 400

        existing = db.query(AttendanceRecord).filter_by(
            session_id=session_id, student_id=student_id
        ).first()
        if existing:
            existing.status = status
            db.commit()
            log_action("create", "attendance_record", entity_id=existing.id, entity_label=f"student:{student_id} session:{session_id}")
            return jsonify({"success": True, "message": "Record updated"})

        record = AttendanceRecord(
            session_id=session_id,
            student_id=student_id,
            check_in_time=datetime.now(),
            status=status,
        )
        db.add(record)
        db.commit()
        log_action("create", "attendance_record", entity_id=record.id, entity_label=f"student:{student_id} session:{session_id}")
        return jsonify({"success": True, "message": "Manual attendance added"})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@secretary_bp.route("/api/attendance/<int:record_id>", methods=["DELETE"])
@require_role("dean", "dean_assistant", "secretary")
def delete_attendance_record(record_id):
    db = get_session()
    try:
        record = db.query(AttendanceRecord).filter_by(id=record_id).first()
        if not record:
            return jsonify({"success": False, "error": "Record not found"}), 404
        label = f"student:{record.student_id} session:{record.session_id}"
        db.delete(record)
        db.commit()
        log_action("delete", "attendance_record", entity_id=record_id, entity_label=label)
        return jsonify({"success": True, "message": "Record deleted"})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@secretary_bp.route("/api/attendance/session/<int:sid>", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_session_details(sid):
    db = get_session()
    try:
        sess = db.query(AttendanceSession).filter_by(id=sid).first()
        if not sess:
            return jsonify({"success": False, "error": "Session not found"}), 404
        doctor = db.query(Doctor).filter_by(id=sess.doctor_id).first()
        course = db.query(Course).filter_by(id=sess.course_id).first() if sess.course_id else None
        hall_name = None
        if sess.schedule_id:
            sched = db.query(Schedule).filter_by(id=sess.schedule_id).first()
            if sched:
                hall = db.query(Hall).filter_by(id=sched.hall_id).first()
                hall_name = hall.hall_name if hall else None

        records = db.query(AttendanceRecord).filter_by(session_id=sid).all()
        present_list, absent_list = [], []
        for r in records:
            stu = db.query(Student).filter_by(id=r.student_id).first()
            entry = {
                "record_id": r.id,
                "student_id": r.student_id,
                "student_name": stu.full_name if stu else "?",
                "academic_id": stu.academic_id if stu else "",
                "check_in_time": r.check_in_time.isoformat() if r.check_in_time else "",
                "status": r.status,
            }
            if r.status == "present":
                present_list.append(entry)
            else:
                absent_list.append(entry)

        enrolled = db.query(Enrollment).filter_by(
            course_id=sess.course_id
        ).all() if sess.course_id else []
        enrolled_ids = {r.student_id for r in records}
        for e in enrolled:
            if e.student_id not in enrolled_ids:
                stu = db.query(Student).filter_by(id=e.student_id).first()
                absent_list.append({
                    "record_id": None,
                    "student_id": e.student_id,
                    "student_name": stu.full_name if stu else "?",
                    "academic_id": stu.academic_id if stu else "",
                    "check_in_time": "",
                    "status": "absent",
                })

        return jsonify({
            "success": True,
            "session": {
                "id": sess.id,
                "course_name": course.course_name if course else "—",
                "course_code": course.course_code if course else "",
                "doctor_name": doctor.full_name if doctor else "—",
                "hall_name": hall_name or "—",
                "date": sess.session_date.isoformat(),
                "start_time": sess.start_timestamp.isoformat(),
                "end_time": sess.end_timestamp.isoformat() if sess.end_timestamp else None,
                "is_active": sess.is_active,
            },
            "present": present_list,
            "absent": absent_list,
        })
    finally:
        db.close()


# ── Backup / Restore ─────────────────────────────────────────────────────────
@secretary_bp.route("/api/backup/create", methods=["POST"])
@require_role("dean")
def create_backup():
    try:
        os.makedirs(config.BACKUP_FOLDER, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(config.BACKUP_FOLDER, f"backup_{ts}.db")
        shutil.copy2(str(config.DATABASE_PATH), dest)
        size = os.path.getsize(dest)
        log_action("create", "backup", entity_label=dest)
        return jsonify({"success": True, "message": "Backup created",
                         "filename": f"backup_{ts}.db", "size": size})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@secretary_bp.route("/api/backup/list", methods=["GET"])
@require_role("dean")
def list_backups():
    try:
        os.makedirs(config.BACKUP_FOLDER, exist_ok=True)
        files = glob_mod.glob(os.path.join(config.BACKUP_FOLDER, "backup_*.db"))
        result = []
        for f in sorted(files, reverse=True):
            result.append({
                "filename": os.path.basename(f),
                "size": os.path.getsize(f),
                "date": datetime.fromtimestamp(os.path.getmtime(f)).isoformat(),
            })
        return jsonify({"success": True, "backups": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@secretary_bp.route("/api/backup/restore", methods=["POST"])
@require_role("dean")
def restore_backup():
    data = request.get_json()
    filename = data.get("filename") if data else None
    if not filename:
        return jsonify({"success": False, "error": "filename required"}), 400
    src = os.path.join(config.BACKUP_FOLDER, filename)
    if not os.path.exists(src):
        return jsonify({"success": False, "error": "Backup file not found"}), 404
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        pre_backup = os.path.join(config.BACKUP_FOLDER, f"pre_restore_{ts}.db")
        shutil.copy2(str(config.DATABASE_PATH), pre_backup)
        shutil.copy2(src, str(config.DATABASE_PATH))
        log_action("update", "backup", entity_label=filename)
        return jsonify({"success": True,
                         "message": "Restored. Please restart the server."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Seed Demo Data ───────────────────────────────────────────────────────────
@secretary_bp.route("/api/admin/seed-demo", methods=["POST"])
@require_role("dean")
def seed_demo_endpoint():
    data = request.get_json(silent=True) or {}
    try:
        from database.seed_demo import seed_demo_data
        summary = seed_demo_data()
        return jsonify({"success": True, "message": "Demo data loaded", "summary": summary})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@secretary_bp.route("/api/admin/wipe-data", methods=["POST"])
@require_role("dean")
def wipe_data():
    db = get_session()
    try:
        for model in [AttendanceRecord, AttendanceSession, Enrollment,
                      Schedule, Alert, Holiday, AbsenceJustification, Device,
                      Course, Student, Doctor, Branch]:
            db.query(model).delete()
        db.commit()
        log_action("delete", "wipe_data", entity_label="all data")
        return jsonify({"success": True, "message": "All data wiped (users kept)"})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


# ── Time Override (Dev) ──────────────────────────────────────────────────────
@secretary_bp.route("/api/dev/time", methods=["GET"])
def get_dev_time():
    from utils.time_provider import is_overridden, now as tp_now
    return jsonify({
        "success": True,
        "current": tp_now().isoformat(),
        "overridden": is_overridden(),
    })


@secretary_bp.route("/api/dev/time/offset", methods=["POST"])
def set_time_offset():
    if not config.DEBUG_MODE:
        return jsonify({"success": False, "error": "Not in debug mode"}), 403
    data = request.get_json()
    seconds = data.get("seconds", 0) if data else 0
    from utils.time_provider import set_offset
    set_offset(seconds)
    return jsonify({"success": True, "offset": seconds})


@secretary_bp.route("/api/dev/time/freeze", methods=["POST"])
def freeze_time():
    if not config.DEBUG_MODE:
        return jsonify({"success": False, "error": "Not in debug mode"}), 403
    data = request.get_json()
    dt_str = data.get("datetime") if data else None
    if not dt_str:
        return jsonify({"success": False, "error": "datetime required"}), 400
    from utils.time_provider import freeze_at
    freeze_at(dt_str)
    return jsonify({"success": True, "frozen_at": dt_str})


@secretary_bp.route("/api/dev/time/reset", methods=["POST"])
def reset_time():
    from utils.time_provider import reset
    reset()
    return jsonify({"success": True, "message": "Time reset to real"})


@secretary_bp.route("/api/students", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_students():
    session = get_session()
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        search = request.args.get("search", "")

        query = session.query(Student)
        if search:
            query = query.filter(
                (Student.academic_id.contains(search)) | (Student.full_name.contains(search))
            )

        total = query.count()
        students = query.offset((page - 1) * per_page).limit(per_page).all()

        result = []
        for s in students:
            branch = session.query(Branch).filter_by(id=s.branch_id).first() if s.branch_id else None
            result.append({
                "id": s.id,
                "academic_id": s.academic_id,
                "full_name": s.full_name,
                "is_temporary": s.is_temporary_card,
                "expiry_date": s.card_expiry_date.isoformat() if s.card_expiry_date else None,
                "branch_id": s.branch_id,
                "branch_name": branch.branch_name if branch else "—",
                "hashed_uid": s.hashed_uid,
                "is_placeholder_card": _is_placeholder_card(s.hashed_uid),
                "card_hint": _card_hint(s.hashed_uid),
            })

        return jsonify({"success": True, "students": result, "total": total, "page": page, "per_page": per_page})
    finally:
        session.close()


@secretary_bp.route("/api/student/add", methods=["POST"])
@secretary_bp.route("/api/students", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def add_student():
    """إنشاء طالب جديد مع بطاقة RFID."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "بيانات مفقودة"}), 400

    academic_id = str(data.get("academic_id", "")).strip()
    full_name = str(data.get("full_name", "")).strip()
    uid = str(data.get("uid", "")).strip()

    if not academic_id or not full_name or not uid:
        return jsonify({"success": False,
                        "error": "الرقم الأكاديمي، الاسم، والبطاقة مطلوبة"}), 400

    session = get_session()
    try:
        # تحقق من عدم التكرار: الرقم الأكاديمي
        if session.query(Student).filter_by(academic_id=academic_id).first():
            return jsonify({"success": False,
                            "error": f"الرقم الأكاديمي {academic_id} مستخدم مسبقاً"}), 400

        # تحقق من البطاقة عند طالب آخر
        hashed_uid = hash_rfid_uid(uid)
        if session.query(Student).filter_by(hashed_uid=hashed_uid).first():
            return jsonify({"success": False,
                            "error": "هذه البطاقة مستخدمة من قبل طالب آخر"}), 400

        # تحقق من البطاقة عند دكتور
        from database.models import Doctor
        if session.query(Doctor).filter_by(hashed_uid=hashed_uid).first():
            return jsonify({"success": False,
                            "error": "هذه البطاقة مستخدمة من قبل دكتور"}), 400

        # تحقق من الاسم الكامل (لا تكرار)
        if session.query(Student).filter(Student.full_name.ilike(full_name)).first():
            return jsonify({"success": False,
                            "error": f"يوجد طالب بنفس الاسم: {full_name}"}), 400

        expiry = None
        if data.get("is_temporary") and data.get("expiry_date"):
            try:
                expiry = datetime.strptime(data["expiry_date"], "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"success": False,
                                "error": "صيغة تاريخ الانتهاء غير صحيحة (YYYY-MM-DD)"}), 400

        student = Student(
            academic_id=academic_id,
            full_name=full_name,
            first_name=(data.get("first_name") or "").strip() or None,
            father_name=(data.get("father_name") or "").strip() or None,
            mother_name=(data.get("mother_name") or "").strip() or None,
            last_name=(data.get("last_name") or "").strip() or None,
            hashed_uid=hashed_uid,
            is_temporary_card=bool(data.get("is_temporary", False)),
            card_expiry_date=expiry,
            branch_id=data.get("branch_id"),
        )
        session.add(student)
        session.commit()
        session.refresh(student)
        log_action("create", "student", entity_id=student.id, entity_label=full_name)
        return jsonify({"success": True,
                        "message": "تم إضافة الطالب بنجاح",
                        "id": student.id})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@secretary_bp.route("/api/student/<int:student_id>", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_student(student_id):
    session = get_session()
    try:
        s = session.query(Student).filter_by(id=student_id).first()
        if not s:
            return jsonify({"success": False, "error": "Student not found"}), 404
        branch = session.query(Branch).filter_by(id=s.branch_id).first() if s.branch_id else None
        return jsonify({"success": True, "student": {
            "id": s.id, "academic_id": s.academic_id, "full_name": s.full_name,
            "first_name": s.first_name, "father_name": s.father_name,
            "mother_name": s.mother_name, "last_name": s.last_name,
            "is_temporary": s.is_temporary_card,
            "expiry_date": s.card_expiry_date.isoformat() if s.card_expiry_date else None,
            "branch_id": s.branch_id,
            "branch_name": branch.branch_name if branch else None,
            "hashed_uid": s.hashed_uid,
            "is_placeholder_card": _is_placeholder_card(s.hashed_uid),
            "card_hint": _card_hint(s.hashed_uid),
        }})
    finally:
        session.close()


@secretary_bp.route("/api/student/<int:student_id>", methods=["PUT"])
@require_role("dean", "dean_assistant", "secretary")
def update_student(student_id):
    data = request.get_json() or {}
    session = get_session()
    try:
        student = session.query(Student).filter_by(id=student_id).first()
        if not student:
            return jsonify({"success": False, "error": "Student not found"}), 404

        original_full_name = student.full_name

        if "full_name" in data and data["full_name"]:
            new_name = data["full_name"].strip()
            # تحقق من تكرار الاسم (طالب آخر)
            other = session.query(Student).filter(
                Student.full_name.ilike(new_name),
                Student.id != student_id).first()
            if other:
                return jsonify({"success": False,
                                 "error": f"يوجد طالب آخر بنفس الاسم: {new_name}"}), 400
            student.full_name = new_name

        for fld in ("first_name", "father_name", "mother_name", "last_name"):
            if fld in data:
                setattr(student, fld, (data[fld] or "").strip() or None)

        if "uid" in data and data["uid"]:
            new_uid = data["uid"].strip()
            new_hash = hash_rfid_uid(new_uid)
            force_uid_change = bool(data.get("force_uid_change"))

            # نفس البطاقة الحالية؟
            if new_hash == student.hashed_uid:
                return jsonify({"success": False,
                                 "error": "البطاقة المُدخلة هي نفس البطاقة الحالية للطالب"}), 400

            # هل البطاقة مستخدمة عند طالب آخر؟
            existing = session.query(Student).filter(
                Student.hashed_uid == new_hash,
                Student.id != student_id).first()
            if existing:
                if force_uid_change:
                    existing.hashed_uid = _placeholder_card_value("student", existing.id)
                    session.flush()
                else:
                    return jsonify({"success": False,
                                     "error": f"هذه البطاقة مستخدمة من قبل الطالب: {existing.full_name}"}), 400

            # هل البطاقة مستخدمة عند دكتور؟
            from database.models import Doctor
            existing_doc = session.query(Doctor).filter_by(hashed_uid=new_hash).first()
            if existing_doc:
                return jsonify({"success": False,
                                 "error": f"هذه البطاقة مستخدمة من قبل الدكتور: {existing_doc.full_name}"}), 400

            student.hashed_uid = new_hash

        if "is_temporary" in data:
            student.is_temporary_card = data["is_temporary"]
        if "expiry_date" in data and data["expiry_date"]:
            student.card_expiry_date = datetime.strptime(data["expiry_date"], "%Y-%m-%d").date()
        if "branch_id" in data:
            student.branch_id = data["branch_id"]

        session.commit()
        return jsonify({"success": True, "message": "تم تحديث بيانات الطالب"})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@secretary_bp.route("/api/student/<int:student_id>", methods=["DELETE"])
@require_role("dean", "dean_assistant", "secretary")
def delete_student(student_id):
    session = get_session()
    try:
        student = session.query(Student).filter_by(id=student_id).first()
        if not student:
            return jsonify({"success": False, "error": "Student not found"}), 404
        session.delete(student)
        name = student.full_name
        session.delete(student)
        session.commit()
        log_action("delete", "student", entity_id=student_id, entity_label=name)
        return jsonify({"success": True, "message": "Student deleted successfully"})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


# ── Courses ───────────────────────────────────────────────────────────────────
@secretary_bp.route("/api/courses", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_courses():
    session = get_session()
    try:
        courses = session.query(Course).all()
        return jsonify({
            "success": True,
            "courses": [{
                "id": c.id,
                "course_code": c.course_code,
                "course_name": c.course_name,
                "course_type": c.course_type,
                "total_weeks": c.total_weeks,
            } for c in courses],
        })
    finally:
        session.close()


# ── Import ────────────────────────────────────────────────────────────────────
@secretary_bp.route("/api/import/excel", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def import_excel():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    file = request.files["file"]
    import_type = request.form.get("type", "students")

    if not file.filename:
        return jsonify({"success": False, "error": "No file selected"}), 400

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    filepath = os.path.join(config.UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    session = get_session()
    try:
        if import_type == "students":
            success, message, data = import_students(filepath, session)
        elif import_type == "courses":
            success, message, data = import_courses(filepath, session)
        else:
            return jsonify({"success": False, "error": "Invalid import type"}), 400

        if success:
            return jsonify({"success": True, "message": message, "data": data})
        return jsonify({"success": False, "error": message}), 400
    finally:
        session.close()


@secretary_bp.route("/api/import/full", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def import_full():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "error": "No file selected"}), 400

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    filepath = os.path.join(config.UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    session = get_session()
    try:
        success, message, data = import_full_data(filepath, session)
        if success:
            return jsonify({"success": True, "message": message, "data": data})
        return jsonify({"success": False, "error": message}), 400
    finally:
        session.close()


# ── Reports ───────────────────────────────────────────────────────────────────
@secretary_bp.route("/api/report/attendance", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_attendance_report():
    course_id = request.args.get("course_id", type=int)
    week_number = request.args.get("week", 1, type=int)

    if not course_id:
        return jsonify({"success": False, "error": "Course ID required"}), 400

    report_data, message = generate_weekly_report(course_id, week_number)
    if report_data is not None:
        return jsonify({"success": True, "data": report_data})
    return jsonify({"success": False, "error": message}), 400


@secretary_bp.route("/api/report/export", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def export_report():
    course_id = request.args.get("course_id", type=int)
    week_number = request.args.get("week", 1, type=int)

    if not course_id:
        return jsonify({"success": False, "error": "Course ID required"}), 400

    session = get_session()
    success, message, filepath = export_attendance_report(session, course_id, week_number)
    session.close()

    if success and filepath:
        return send_file(filepath, as_attachment=True)
    return jsonify({"success": False, "error": message}), 400


# ── Alerts ────────────────────────────────────────────────────────────────────
@secretary_bp.route("/api/alerts", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_alerts():
    return jsonify({"success": True, "alerts": get_active_alerts()})


@secretary_bp.route("/api/alerts/<int:alert_id>/read", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def read_alert(alert_id):
    success, message = mark_alert_as_read(alert_id)
    if success:
        return jsonify({"success": True, "message": message})
    return jsonify({"success": False, "error": message}), 400


# ── Template ──────────────────────────────────────────────────────────────────
@secretary_bp.route("/api/template/download", methods=["GET"])
def download_template():
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    filepath = os.path.join(config.UPLOAD_FOLDER, "import_template.xlsx")
    success, message = generate_sample_excel_template(filepath)
    if success:
        return send_file(filepath, as_attachment=True)
    return jsonify({"success": False, "error": message}), 400


# ── Dashboard stats ───────────────────────────────────────────────────────────
@secretary_bp.route("/api/dashboard/stats", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_dashboard_stats():
    session = get_session()
    try:
        total_students = session.query(Student).count()
        active_sessions = session.query(AttendanceSession).filter_by(is_active=True).count()
        from datetime import date
        today_attendance = (
            session.query(AttendanceRecord)
            .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
            .filter(AttendanceSession.session_date == date.today())
            .count()
        )
        active_alerts = session.query(
            __import__("database.models", fromlist=["Alert"]).Alert
        ).filter_by(is_read=False).count()

        return jsonify({
            "success": True,
            "stats": {
                "total_students": total_students,
                "active_sessions": active_sessions,
                "today_attendance": today_attendance,
                "active_alerts": active_alerts,
            },
        })
    finally:
        session.close()


# ── Settings ───────────────────────────────────────────────────────────────────
@secretary_bp.route("/api/settings", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary")
def get_settings():
    session = get_session()
    try:
        settings = session.query(Setting).all()
        return jsonify({
            "success": True,
            "settings": [{"key": s.key, "value": s.value, "description": s.description} for s in settings],
        })
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@secretary_bp.route("/api/settings/<string:key>", methods=["PUT"])
@require_role("dean")
def update_setting(key):
    from database.models import Setting
    data = request.get_json()
    if not data or "value" not in data:
        return jsonify({"success": False, "error": "value field required"}), 400
    new_value = str(data["value"]).strip()
    session = get_session()
    try:
        setting = session.query(Setting).filter_by(key=key).first()
        if not setting:
            setting = Setting(key=key, value=new_value, description=data.get("description", ""))
            session.add(setting)
        else:
            setting.value = new_value
            if "description" in data:
                setting.description = data["description"]
        session.commit()
        return jsonify({"success": True, "message": f"Setting '{key}' updated"})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()
