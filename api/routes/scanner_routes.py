from flask import Blueprint, request, jsonify
from database import get_session
from database.models import (
    Device, Doctor, Student, AttendanceSession,
    Schedule, Enrollment, Course, ScanLog,
)
from security.security_manager import hash_rfid_uid, verify_device_token
from api.auth import require_role
from api.controllers.attendance_controller import (
    open_session, close_session, record_attendance, check_duplicate_scan,
)
from datetime import datetime
from collections import deque
import threading
from utils.time_provider import now as tp_now, today as tp_today
from utils.logger import get_logger

log = get_logger("scanner")
log_scan = get_logger("scanner.scan")

scanner_bp = Blueprint("scanner", __name__)


def _uid_hint(uid):
    """Return last 4 chars of raw UID for display (never expose the full UID)."""
    if not uid:
        return None
    s = str(uid).strip().upper()
    return s[-4:] if len(s) >= 4 else s


def _log_scan(scan_type, success, *, hashed_uid=None, raw_uid_hint=None,
              device_id=None, hall_id=None, student_id=None, doctor_id=None,
              session_id=None, error_reason=None):
    """Persist a scan attempt to scan_logs. Never raises; failures are silent."""
    s = get_session()
    try:
        log = ScanLog(
            timestamp=tp_now(),
            hashed_uid=hashed_uid,
            raw_uid_hint=raw_uid_hint,
            device_id=device_id,
            hall_id=hall_id,
            scan_type=scan_type,
            success=success,
            student_id=student_id,
            doctor_id=doctor_id,
            session_id=session_id,
            error_reason=error_reason,
        )
        s.add(log)
        s.commit()
    except Exception:
        try:
            s.rollback()
        except Exception:
            pass
    finally:
        try:
            s.close()
        except Exception:
            pass

_recent_scans = deque(maxlen=50)
_recent_scans_lock = threading.Lock()

# ─── عداد التحديثات الحية (للـ polling السريع) ───
_live_counter = {"value": 0, "last_event": None}
_live_counter_lock = threading.Lock()


def _bump_live_counter(event=None):
    with _live_counter_lock:
        _live_counter["value"] += 1
        _live_counter["last_event"] = event


def _add_recent_scan(uid, device_id, card_type, name, success, detail=""):
    with _recent_scans_lock:
        _recent_scans.appendleft({
            "uid": uid,
            "device_id": device_id,
            "card_type": card_type or "unknown",
            "name": name or "",
            "success": success,
            "detail": detail,
            "timestamp": tp_now().isoformat(),
        })
    # عند كل مسح، حدّث الـ counter
    _bump_live_counter({
        "uid": uid,
        "card_type": card_type,
        "name": name,
        "success": success,
        "detail": detail,
    })

def validate_device(device_id, device_token):
    session = get_session()
    try:
        device = session.query(Device).filter_by(device_id=device_id).first()
        if not device or not device.is_active:
            return False, None, "Device not found or inactive"
        if not verify_device_token(device_id, device_token, device.device_token):
            return False, None, "Invalid device token"
        device.last_seen = datetime.now()
        session.commit()
        hall_id = device.hall_id
        return True, {"id": device.id, "hall_id": hall_id, "device_id": device_id}, "OK"
    except Exception as e:
        session.rollback()
        return False, None, str(e)
    finally:
        session.close()


def identify_card_type(hashed_uid):
    session = get_session()
    try:
        doctor = session.query(Doctor).filter_by(hashed_uid=hashed_uid).first()
        if doctor:
            return "doctor", {"id": doctor.id, "full_name": doctor.full_name}

        student = session.query(Student).filter_by(hashed_uid=hashed_uid).first()
        if student:
            return "student", {
                "id": student.id,
                "full_name": student.full_name,
                "is_temporary_card": student.is_temporary_card,
                "card_expiry_date": student.card_expiry_date,
            }
        return None, None
    finally:
        session.close()


@scanner_bp.route("/api/scan", methods=["POST", "GET"])
def scan_card():
    try:
        return _scan_card_inner()
    except Exception as exc:
        log.exception("scan_card failed: uid=%s device=%s", request.args.get("uid") or (request.get_json(silent=True) or {}).get("uid"), request.args.get("device_id") or (request.get_json(silent=True) or {}).get("device_id"))
        _add_recent_scan("", "", "unknown", "", False, f"server_error: {exc}")
        return jsonify({"success": False, "error": "internal_error", "message": str(exc)}), 500


def _scan_card_inner():
    if request.method == "GET":
        uid = request.args.get("uid")
        device_id = request.args.get("device_id")
        device_token = request.args.get("device_token")
        device_role = request.args.get("device_role", "")
        data = {"uid": uid, "device_id": device_id, "device_token": device_token, "device_role": device_role}
    else:
        data = request.get_json() or {}
        uid = data.get("uid")
        device_id = data.get("device_id")
        device_token = data.get("device_token")
        device_role = data.get("device_role", "")

    if not device_role and device_id:
        if device_id.upper() == "SECRETARY":
            device_role = "SECRETARY"
        else:
            device_role = "HALL"

    log_scan.info("uid=%s device=%s role=%s", uid, device_id, device_role)

    try:
        if not all([uid, device_id, device_token]):
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        is_valid, device, message = validate_device(device_id, device_token)
        if not is_valid:
            log_scan.warning("Device validation failed: uid=%s device=%s msg=%s", uid, device_id, message)
            _add_recent_scan(uid, device_id, None, "", False, f"rejected: {message}")
            _log_scan("unauthorized_device", False, hashed_uid=hash_rfid_uid(uid) if uid else None,
                      raw_uid_hint=_uid_hint(uid), device_id=device_id,
                      error_reason=f"unauthorized: {message}")
            return jsonify({"success": False, "error": "unauthorized_device", "message": message}), 401

        hashed_uid = hash_rfid_uid(uid)
        card_type, card_holder = identify_card_type(hashed_uid)
        uid_hint = _uid_hint(uid)
        hall_id = device.get("hall_id") if device else None

        # اجعل آخر بطاقة ممرَّرة متاحة لحوارات السكرتارية (ملف الطالب/الدكتور بالبطاقة)
        # مع تمرير نوع البطاقة حتى تظهر تفاصيل المعروفة، ويبقى بانر "تسجيل بطاقة جديدة"
        # مقتصراً على البطاقات غير المعروفة فقط.
        _set_pending_card(uid, device_id, card_type or "unknown")

        if card_type == "doctor":
            _add_recent_scan(uid, device_id, "doctor", card_holder["full_name"], True, "session_open/close")
            return process_doctor_scan(card_holder, device, hashed_uid=hashed_uid, uid_hint=uid_hint)
        elif card_type == "student":
            return process_student_scan(card_holder, device, uid, device_id,
                                        hashed_uid=hashed_uid, uid_hint=uid_hint)
        else:
            _add_recent_scan(uid, device_id, "unknown", "", False, "card not registered")
            _log_scan("unknown_card", False, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                      device_id=device_id, hall_id=hall_id,
                      error_reason="card_not_registered")
            return jsonify({
                "success": False,
                "error": "unknown_card",
                "message": "Card not registered",
                "signal": "RED_LIGHT_BUZZER",
            }), 404
    except Exception as exc:
        log.exception("scan_card failed: uid=%s device=%s", uid, device_id)
        return jsonify({"success": False, "error": "internal", "message": str(exc)}), 500


@scanner_bp.route("/api/scan/recent", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def get_recent_scans():
    with _recent_scans_lock:
        scans = list(_recent_scans)
    limit = request.args.get("limit", 20, type=int)
    scans = scans[:limit]
    return jsonify({"success": True, "scans": scans, "count": len(scans)})


_pending_card_uid = {"uid": None, "timestamp": None, "card_type": None}
_pending_card_lock = threading.Lock()


def _set_pending_card(uid, device_id, card_type=None, device_role=None):
    """يتيح آخر UID ممرَّر لحوارات السكرتارية (تسجيل بطاقة / فتح ملف بالبطاقة).

    card_type يميّز البطاقة المعروفة (doctor/student) عن غير المعروفة (unknown)
    حتى تعرض الواجهة تفاصيل المعروفة، ويبقى بانر «تسجيل بطاقة جديدة» للبطاقات
    غير المعروفة فقط.
    """
    with _pending_card_lock:
        _pending_card_uid["uid"] = uid
        _pending_card_uid["device_id"] = device_id
        _pending_card_uid["card_type"] = card_type
        _pending_card_uid["timestamp"] = tp_now().isoformat()
        if device_role is not None:
            _pending_card_uid["device_role"] = device_role


@scanner_bp.route("/api/scan/register-card", methods=["POST"])
def register_card():
    global _pending_card_uid
    data = request.get_json()
    if not data or not data.get("uid"):
        return jsonify({"success": False, "error": "Missing uid"}), 400

    uid = data["uid"].strip().upper()
    device_id = (data.get("device_id") or "").strip()
    device_token = (data.get("device_token") or "").strip()
    device_role = data.get("device_role", "")

    # قارئ التسجيل (SECRETARY): جهاز موثوق، يعمل بدون token — السر يبقى في الواجهة
    # (قراءة pending-card تتطلب جلسة secretary). باقي الأجهزة تتطلب token صحيح.
    if device_id.upper() == "SECRETARY":
        device_role = device_role or "SECRETARY"
    else:
        if not all([device_id, device_token]):
            return jsonify({"success": False, "error": "Missing device_id or device_token"}), 400
        is_valid, device, message = validate_device(device_id, device_token)
        if not is_valid:
            log_scan.warning("register-card device validation failed: device=%s msg=%s", device_id, message)
            return jsonify({"success": False, "error": "unauthorized_device", "message": message}), 401
    log_scan.info("register-card uid=%s device=%s role=%s", uid, device_id, device_role)

    # بطاقة دكتور معروفة → افتح/أغلق الجلسة (يعمل من قارئ السكرتارية بدون قاعة مثبتة)
    hashed_uid = hash_rfid_uid(uid)
    doctor_info = None
    s = get_session()
    try:
        doctor = s.query(Doctor).filter_by(hashed_uid=hashed_uid).first()
        if doctor:
            current = tp_now()
            schedule = s.query(Schedule).join(Course).filter(
                Schedule.day_of_week == current.weekday(),
                Schedule.start_time <= current.time(),
                Schedule.end_time >= current.time(),
                Course.doctor_id == doctor.id,
            ).first()
            active = s.query(AttendanceSession).filter_by(
                doctor_id=doctor.id, is_active=True
            ).first()
            doctor_info = {
                "id": doctor.id,
                "name": doctor.full_name,
                "schedule_id": schedule.id if schedule else None,
                "course_id": schedule.course_id if schedule else None,
                "active_session_id": active.id if active else None,
            }
    finally:
        try:
            s.close()
        except Exception:
            pass

    if doctor_info is not None:
        d_id = doctor_info["id"]
        d_name = doctor_info["name"]
        # أتِح بطاقة الدكتور لحوار «ملف الدكتور بالبطاقة» (إن كان مفتوحاً)
        _set_pending_card(uid, device_id, "doctor", device_role)
        if doctor_info["active_session_id"]:
            sid = doctor_info["active_session_id"]
            ok, msg = close_session(sid)
            if ok:
                _add_recent_scan(uid, device_id, "doctor", d_name, True, "session_closed_from_secretary")
                _log_scan("doctor_close", True, hashed_uid=hashed_uid, raw_uid_hint=_uid_hint(uid),
                          device_id=device_id, doctor_id=d_id, session_id=sid)
                return jsonify({"success": True, "message": "Session closed", "action": "close", "doctor": d_name})
            return jsonify({"success": False, "error": "close_failed", "message": msg}), 500
        if not doctor_info["schedule_id"]:
            _add_recent_scan(uid, device_id, "doctor", d_name, False, "no_schedule_now")
            _log_scan("no_schedule_now", False, hashed_uid=hashed_uid, raw_uid_hint=_uid_hint(uid),
                      device_id=device_id, doctor_id=d_id, error_reason="no_schedule_at_current_time")
            return jsonify({"success": False, "error": "no_schedule_now",
                            "message": "لا توجد محاضرة مقررة لهذا الدكتور في هذا الوقت"}), 400
        sid, msg = open_session(d_id, schedule_id=doctor_info["schedule_id"],
                                course_id=doctor_info["course_id"])
        if sid:
            _add_recent_scan(uid, device_id, "doctor", d_name, True, "session_opened_from_secretary")
            _log_scan("doctor_open", True, hashed_uid=hashed_uid, raw_uid_hint=_uid_hint(uid),
                      device_id=device_id, doctor_id=d_id, session_id=sid)
            return jsonify({"success": True, "message": "Session opened", "action": "open",
                            "doctor": d_name, "session_id": sid})
        return jsonify({"success": False, "error": "open_failed", "message": msg}), 500

    # بطاقة غير معروفة → ضعها في pending للتسجيل عبر الـ dialog
    with _pending_card_lock:
        _pending_card_uid = {
            "uid": uid,
            "device_id": device_id,
            "device_role": device_role,
            "timestamp": tp_now().isoformat(),
        }
    _add_recent_scan(uid, device_id, "register", "", True, f"card registration (role={device_role})")
    return jsonify({"success": True, "message": "Card registered", "uid": uid})


@scanner_bp.route("/api/scan/pending-card", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary")
def get_pending_card():
    with _pending_card_lock:
        card = dict(_pending_card_uid) if _pending_card_uid.get("uid") else None
    if card and card.get("uid"):
        with _pending_card_lock:
            _pending_card_uid["uid"] = None
            _pending_card_uid["timestamp"] = None
            _pending_card_uid["card_type"] = None
            _pending_card_uid.pop("device_id", None)
            _pending_card_uid.pop("device_role", None)
        return jsonify({"success": True, "card": card})
    return jsonify({"success": True, "card": None})


@scanner_bp.route("/api/scan/clear-pending", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary")
def clear_pending_card():
    """يمسح أي UID معلَّق من جلسة سابقة — يُستدعى عند فتح حوار المسح."""
    global _pending_card_uid
    with _pending_card_lock:
        _pending_card_uid = {"uid": None, "timestamp": None, "card_type": None}
    return jsonify({"success": True, "message": "Pending cleared"})


def process_doctor_scan(doctor, device, *, hashed_uid=None, uid_hint=None):
    log_scan.info("process_doctor_scan: doctor_id=%s device=%s", doctor.get("id"), device)
    session = get_session()
    try:
        hall_id = device.get("hall_id")
        device_id_str = device.get("device_id", "")
        current = tp_now()
        current_day = current.weekday()
        current_time = current.time()

        # محاولة 1: مطابقة دقيقة (قاعة + يوم + وقت)
        schedule = session.query(Schedule).join(Course).filter(
            Schedule.hall_id == hall_id,
            Schedule.day_of_week == current_day,
            Schedule.start_time <= current_time,
            Schedule.end_time >= current_time,
            Course.doctor_id == doctor["id"],
        ).first()

        # محاولة 2: مطابقة مرنة — أي محاضرة لهذا الدكتور الآن (تتجاهل القاعة)
        if not schedule:
            schedule = session.query(Schedule).join(Course).filter(
                Schedule.day_of_week == current_day,
                Schedule.start_time <= current_time,
                Schedule.end_time >= current_time,
                Course.doctor_id == doctor["id"],
            ).first()
            if schedule:
                log_scan.info("doctor scan: hall mismatch tolerated. device_hall=%s schedule_hall=%s",
                              hall_id, schedule.hall_id)

        # محاولة 3 (تساهلية): أي محاضرة لهذا الدكتور اليوم (لو الجدول ضعيف الدقة الزمنية)
        if not schedule:
            schedule = session.query(Schedule).join(Course).filter(
                Schedule.day_of_week == current_day,
                Course.doctor_id == doctor["id"],
            ).first()

        if not schedule:
            _add_recent_scan("", device_id_str, "doctor",
                             doctor["full_name"], False, "no_matching_schedule")
            _log_scan("wrong_hall", False, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                      device_id=device_id_str, hall_id=hall_id, doctor_id=doctor["id"],
                      error_reason="no_matching_schedule")
            session.close()
            return jsonify({
                "success": False,
                "error": "no_matching_schedule",
                "message": "لا توجد محاضرة مقررة لهذا الدكتور اليوم",
                "signal": "RED_LIGHT_BUZZER",
            }), 400

        active_session = session.query(AttendanceSession).filter_by(
            doctor_id=doctor["id"], is_active=True
        ).first()

        if active_session:
            sid = active_session.id
            session.close()
            success, msg = close_session(sid)
            if success:
                _log_scan("doctor_close", True, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                          device_id=device_id_str, hall_id=hall_id, doctor_id=doctor["id"],
                          session_id=sid)
                return jsonify({"success": True, "message": "Session closed", "signal": "BUZZER_SESSION_CLOSE"})
            _log_scan("doctor_close", False, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                      device_id=device_id_str, hall_id=hall_id, doctor_id=doctor["id"],
                      session_id=sid, error_reason=msg)
            return jsonify({"success": False, "error": "close_failed", "message": msg, "signal": "RED_LIGHT_BUZZER"}), 500
        else:
            schedule_id = schedule.id if schedule else None
            course_id = schedule.course_id if schedule else None
            session.close()
            sid, msg = open_session(doctor["id"], schedule_id=schedule_id, course_id=course_id)
            if sid:
                _log_scan("doctor_open", True, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                          device_id=device_id_str, hall_id=hall_id, doctor_id=doctor["id"],
                          session_id=sid)
                return jsonify({"success": True, "message": "Session opened", "signal": "BUZZER_SESSION_OPEN", "session_id": sid})
            _log_scan("doctor_open", False, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                      device_id=device_id_str, hall_id=hall_id, doctor_id=doctor["id"],
                      error_reason=msg)
            return jsonify({"success": False, "error": "open_failed", "message": msg, "signal": "RED_LIGHT_BUZZER"}), 500
    except Exception as e:
        log.exception("process_doctor_scan failed: doctor=%s device=%s", doctor.get("id"), (device or {}).get("device_id"))
        return jsonify({"success": False, "error": str(e), "signal": "RED_LIGHT_BUZZER"}), 500
    finally:
        try:
            session.close()
        except Exception:
            pass


def process_student_scan(student, device, uid="", device_id="",
                         *, hashed_uid=None, uid_hint=None):
    try:
        return _process_student_scan(student, device, uid, device_id,
                                     hashed_uid=hashed_uid, uid_hint=uid_hint)
    except Exception as e:
        log.exception("process_student_scan failed: student=%s device=%s", student.get("id"), (device or {}).get("device_id"))
        return jsonify({"success": False, "error": str(e), "signal": "RED_LIGHT_BUZZER"}), 500


def _process_student_scan(student, device, uid="", device_id="",
                          *, hashed_uid=None, uid_hint=None):
    name = student["full_name"]
    hall_id = device.get("hall_id") if device else None
    student_id = student["id"]

    if student["is_temporary_card"] and student["card_expiry_date"] \
            and student["card_expiry_date"] < tp_today():
        _add_recent_scan(uid, device_id, "student", name, False, "card_expired")
        _log_scan("expired_card", False, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                  device_id=device_id, hall_id=hall_id, student_id=student_id,
                  error_reason="card_expired")
        return jsonify({
            "success": False,
            "error": "card_expired",
            "message": "Temporary card has expired",
            "signal": "RED_LIGHT_BUZZER",
        }), 400

    course_id = None
    session_id = None

    session = get_session()
    try:
        active_session = (
            session.query(AttendanceSession)
            .join(Schedule, AttendanceSession.schedule_id == Schedule.id)
            .filter(Schedule.hall_id == hall_id, AttendanceSession.is_active == True)
            .first()
        )

        if not active_session:
            active_session = session.query(AttendanceSession).filter_by(is_active=True).first()

        if not active_session:
            _add_recent_scan(uid, device_id, "student", name, False, "no_active_session")
            _log_scan("no_session", False, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                      device_id=device_id, hall_id=hall_id, student_id=student_id,
                      error_reason="no_active_session")
            return jsonify({
                "success": False,
                "error": "no_active_session",
                "message": "No active session in this hall",
                "signal": "RED_LIGHT_BUZZER",
            }), 400

        course_id = active_session.course_id
        session_id = active_session.id
    finally:
        session.close()

    if course_id:
        db = get_session()
        try:
            # 1. تحقق من تسجيل الطالب في المادة
            enrollment = db.query(Enrollment).filter_by(
                student_id=student_id, course_id=course_id
            ).first()
            if not enrollment:
                _add_recent_scan(uid, device_id, "student", name, False, "not_enrolled")
                _log_scan("student_in", False, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                          device_id=device_id, hall_id=hall_id, student_id=student_id,
                          session_id=session_id, error_reason="not_enrolled")
                return jsonify({
                    "success": False,
                    "error": "not_enrolled",
                    "message": "الطالب غير مسجّل في هذه المادة",
                    "signal": "RED_LIGHT_BUZZER",
                }), 400

            # 2. تحقق من تطابق الفرع
            from database.models import Student as StudentModel, Course as CourseModel
            stu_db = db.query(StudentModel).filter_by(id=student_id).first()
            crs_db = db.query(CourseModel).filter_by(id=course_id).first()
            if stu_db and crs_db and stu_db.branch_id and crs_db.branch_id:
                if stu_db.branch_id != crs_db.branch_id:
                    _add_recent_scan(uid, device_id, "student", name, False, "wrong_branch")
                    _log_scan("student_in", False, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                              device_id=device_id, hall_id=hall_id, student_id=student_id,
                              session_id=session_id, error_reason="wrong_branch")
                    return jsonify({
                        "success": False,
                        "error": "wrong_branch",
                        "message": "الطالب من فرع مختلف عن فرع المادة",
                        "signal": "RED_LIGHT_BUZZER",
                    }), 400
        finally:
            db.close()
    else:
        # جلسة بدون مادة (no schedule found) — نرفض الحضور
        _add_recent_scan(uid, device_id, "student", name, False, "no_course")
        _log_scan("student_in", False, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                  device_id=device_id, hall_id=hall_id, student_id=student_id,
                  session_id=session_id, error_reason="no_course")
        return jsonify({
            "success": False,
            "error": "no_course",
            "message": "لا يوجد مادة مرتبطة بهذه الجلسة (راجع جدول الدكتور)",
            "signal": "RED_LIGHT_BUZZER",
        }), 400

    if check_duplicate_scan(session_id, student_id):
        _add_recent_scan(uid, device_id, "student", name, False, "duplicate_scan")
        _log_scan("student_in", False, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                  device_id=device_id, hall_id=hall_id, student_id=student_id,
                  session_id=session_id, error_reason="duplicate_scan")
        return jsonify({
            "success": False,
            "error": "duplicate_scan",
            "message": "Student already scanned",
            "signal": "RED_LIGHT_BUZZER",
        }), 400

    try:
        record_id, message = record_attendance(session_id, student_id)
        if record_id:
            _add_recent_scan(uid, device_id, "student", name, True, "attendance")
            _log_scan("student_in", True, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                      device_id=device_id, hall_id=hall_id, student_id=student_id,
                      session_id=session_id)
            return jsonify({
                "success": True,
                "message": "Attendance recorded",
                "signal": "GREEN_LIGHT",
                "student_name": name,
            })
        _add_recent_scan(uid, device_id, "student", name, False, "record_failed")
        _log_scan("student_in", False, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                  device_id=device_id, hall_id=hall_id, student_id=student_id,
                  session_id=session_id, error_reason="record_failed")
        return jsonify({"success": False, "error": "record_failed", "message": message}), 500
    except Exception as e:
        log.exception("record_attendance failed: student=%s session=%s", student_id, session_id)
        _add_recent_scan(uid, device_id, "student", name, False, "error")
        _log_scan("student_in", False, hashed_uid=hashed_uid, raw_uid_hint=uid_hint,
                  device_id=device_id, hall_id=hall_id, student_id=student_id,
                  session_id=session_id, error_reason=str(e)[:200])
        return jsonify({"success": False, "error": str(e)}), 500


@scanner_bp.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({"status": "online", "server_time": tp_now().isoformat()})


@scanner_bp.route("/api/live/counter", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def live_counter():
    """يرجع counter التحديثات الحية + آخر حدث.
    الواجهة تطلبها كل ثانية وتقارن مع القيمة السابقة."""
    with _live_counter_lock:
        return jsonify({
            "counter": _live_counter["value"],
            "last_event": _live_counter["last_event"],
            "server_time": tp_now().isoformat(),
        })


@scanner_bp.route("/api/live/state", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def live_state():
    """الحالة الكاملة للنظام: الجلسات النشطة + الحضور الحالي.
    تُجلب عند تغيّر الـ counter."""
    from database.models import AttendanceSession, AttendanceRecord, Doctor, Course, Hall, Student
    session = get_session()
    try:
        sessions = session.query(AttendanceSession).filter_by(is_active=True).all()
        result = []
        for sess in sessions:
            doctor = session.query(Doctor).filter_by(id=sess.doctor_id).first()
            course = session.query(Course).filter_by(id=sess.course_id).first() if sess.course_id else None

            # القاعة من الـ schedule
            hall_name = "—"
            if sess.schedule_id:
                from database.models import Schedule
                sched = session.query(Schedule).filter_by(id=sess.schedule_id).first()
                if sched:
                    hall = session.query(Hall).filter_by(id=sched.hall_id).first()
                    if hall:
                        hall_name = hall.hall_name

            # سجلات الحضور لهالـ session
            records = session.query(AttendanceRecord).filter_by(
                session_id=sess.id).order_by(AttendanceRecord.check_in_time.desc()).all()
            attendances = []
            for rec in records:
                stu = session.query(Student).filter_by(id=rec.student_id).first()
                attendances.append({
                    "student_id": rec.student_id,
                    "name": stu.full_name if stu else "?",
                    "academic_id": stu.academic_id if stu else "",
                    "timestamp": rec.check_in_time.isoformat() if rec.check_in_time else "",
                })

            elapsed_seconds = 0
            if sess.start_timestamp:
                elapsed_seconds = max(0, int((tp_now() - sess.start_timestamp).total_seconds()))

            result.append({
                "session_id": sess.id,
                "doctor_name": doctor.full_name if doctor else "؟",
                "course_name": course.course_name if course else "—",
                "course_code": course.course_code if course else "",
                "hall_name": hall_name,
                "start_time": sess.start_timestamp.strftime("%H:%M:%S") if sess.start_timestamp else "",
                "elapsed_seconds": elapsed_seconds,
                "attendance_count": len(attendances),
                "attendances": attendances,
            })

        return jsonify({
            "success": True,
            "active_sessions": result,
            "counter": _live_counter["value"],
            "last_event": _live_counter["last_event"],
        })
    finally:
        session.close()


@scanner_bp.route("/api/sync", methods=["POST"])
def sync_offline_data():
    data = request.get_json()
    if not data or "records" not in data:
        return jsonify({"success": False, "error": "No records provided"}), 400

    records = data.get("records", [])
    synced = 0
    failed = 0

    for rec in records:
        try:
            uid = rec.get("uid")
            device_id = rec.get("device_id")
            if not uid or not device_id:
                failed += 1
                continue

            session = get_session()
            device = session.query(Device).filter_by(device_id=device_id).first()
            if not device:
                session.close()
                failed += 1
                continue
            hall_id = device.hall_id
            session.close()

            hashed = hash_rfid_uid(uid)
            card_type, card_holder = identify_card_type(hashed)

            if card_type == "student":
                session2 = get_session()
                active = (
                    session2.query(AttendanceSession)
                    .join(Schedule, AttendanceSession.schedule_id == Schedule.id)
                    .filter(Schedule.hall_id == hall_id, AttendanceSession.is_active == True)
                    .first()
                )
                if active:
                    sid = active.id
                    session2.close()
                    rid, _ = record_attendance(sid, card_holder["id"])
                    synced += 1 if rid else 0
                    failed += 0 if rid else 1
                else:
                    session2.close()
                    failed += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    return jsonify({"success": True, "synced": synced, "failed": failed, "total": len(records)})
