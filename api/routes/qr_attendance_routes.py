"""QR-based attendance: doctor generates a rotating QR; students scan it with
their phone, open a web page on the server, enter their academic_id, and the
backend records attendance into the linked AttendanceSession.

The QR token rotates every TOKEN_ROTATION_SECONDS, and the whole session expires
after SESSION_DURATION_MINUTES (default 5 minutes). A photo of the QR therefore
becomes useless within seconds — the standard practical defense against
photo-replay attacks.
"""
import io
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, send_file, Response, render_template_string

from database import get_session
from database.models import (
    Doctor, Course, Hall, Student, Enrollment,
    AttendanceSession, AttendanceRecord, QRSession,
)
from api.auth import get_current_user, require_role
from api.audit import log_action
from api.controllers.attendance_controller import (
    open_session, close_session, record_attendance, check_duplicate_scan,
)
from utils.time_provider import now as tp_now, today as tp_today
from utils.logger import get_logger

log = get_logger("qr_attendance")

qr_bp = Blueprint("qr_attendance", __name__)

TOKEN_ROTATION_SECONDS = 8
SESSION_DURATION_MINUTES = 5


def _new_token():
    return secrets.token_urlsafe(24)


def _fresh_qr_session(qrs, db):
    """Return current valid token, rotating if expired. May mutate qrs/db."""
    now = tp_now()
    if not qrs.is_active or qrs.session_expires_at <= now:
        return None
    if qrs.token_rotates_at <= now:
        qrs.current_token = _new_token()
        qrs.token_rotates_at = now + timedelta(seconds=TOKEN_ROTATION_SECONDS)
        db.commit()
    return qrs.current_token


def _checkin_url(token):
    """Build the URL a student's phone will open after scanning."""
    host = request.host_url.rstrip("/")
    return f"{host}/qr/checkin/{token}"


# ── Doctor: start QR session ─────────────────────────────────────────────────
@qr_bp.route("/api/doctor/qr/start", methods=["POST"])
@require_role("doctor", "dean")
def qr_start():
    user = get_current_user()
    if not user or not user.get("doctor_id"):
        return jsonify({"success": False, "error": "No doctor profile"}), 403

    data = request.get_json() or {}
    course_id = data.get("course_id")
    hall_id = data.get("hall_id")
    if not course_id:
        return jsonify({"success": False, "error": "course_id required"}), 400

    db = get_session()
    try:
        course = db.query(Course).filter_by(id=course_id).first()
        if not course:
            return jsonify({"success": False, "error": "Course not found"}), 404
        if course.doctor_id and course.doctor_id != user["doctor_id"]:
            return jsonify({"success": False, "error": "Course is not assigned to you"}), 403

        if hall_id:
            hall = db.query(Hall).filter_by(id=hall_id).first()
            if not hall:
                return jsonify({"success": False, "error": "Hall not found"}), 404

        # هل في QR session نشطة لنفس الدكتور؟ أرجعها بدلاً من إنشاء جديدة.
        existing = (db.query(QRSession)
                    .filter_by(doctor_id=user["doctor_id"], is_active=True)
                    .first())
        if existing and existing.session_expires_at > tp_now():
            token = _fresh_qr_session(existing, db)
            return jsonify({
                "success": True,
                "qr_session_id": existing.id,
                "attendance_session_id": existing.attendance_session_id,
                "token": token,
                "checkin_url": _checkin_url(token),
                "rotation_seconds": TOKEN_ROTATION_SECONDS,
                "expires_at": existing.session_expires_at.isoformat(),
                "reused": True,
            })

        # افتح AttendanceSession جديدة (لو ما في نشطة لهذا الدكتور)
        active = (db.query(AttendanceSession)
                  .filter_by(doctor_id=user["doctor_id"], is_active=True)
                  .first())
        if active:
            attendance_session_id = active.id
        else:
            attendance_session_id, msg = open_session(
                user["doctor_id"], course_id=course_id)
            if not attendance_session_id:
                return jsonify({"success": False, "error": msg}), 400

        now = tp_now()
        token = _new_token()
        qrs = QRSession(
            attendance_session_id=attendance_session_id,
            doctor_id=user["doctor_id"],
            course_id=course_id,
            hall_id=hall_id,
            current_token=token,
            token_rotates_at=now + timedelta(seconds=TOKEN_ROTATION_SECONDS),
            session_expires_at=now + timedelta(minutes=SESSION_DURATION_MINUTES),
            is_active=True,
        )
        db.add(qrs)
        db.commit()
        db.refresh(qrs)

        log_action("create", "qr_session", entity_id=qrs.id,
                   entity_label=f"course:{course_id} hall:{hall_id}")

        return jsonify({
            "success": True,
            "qr_session_id": qrs.id,
            "attendance_session_id": attendance_session_id,
            "token": token,
            "checkin_url": _checkin_url(token),
            "rotation_seconds": TOKEN_ROTATION_SECONDS,
            "expires_at": qrs.session_expires_at.isoformat(),
            "reused": False,
        })
    except Exception as e:
        db.rollback()
        log.exception("qr_start failed")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


# ── Doctor: get current token (rotates as needed) ───────────────────────────
@qr_bp.route("/api/doctor/qr/current/<int:qr_session_id>", methods=["GET"])
@require_role("doctor", "dean")
def qr_current(qr_session_id):
    user = get_current_user()
    db = get_session()
    try:
        qrs = db.query(QRSession).filter_by(id=qr_session_id).first()
        if not qrs:
            return jsonify({"success": False, "error": "QR session not found"}), 404
        if user["role"] != "dean" and qrs.doctor_id != user.get("doctor_id"):
            return jsonify({"success": False, "error": "Forbidden"}), 403

        if not qrs.is_active or qrs.session_expires_at <= tp_now():
            qrs.is_active = False
            db.commit()
            return jsonify({"success": False, "error": "expired",
                            "expires_at": qrs.session_expires_at.isoformat()}), 410

        token = _fresh_qr_session(qrs, db)

        # عدّ المسجلين حتى الآن
        att_count = db.query(AttendanceRecord).filter_by(
            session_id=qrs.attendance_session_id,
            status="present",
        ).count()

        seconds_left = max(0, int((qrs.session_expires_at - tp_now()).total_seconds()))
        token_seconds_left = max(0, int((qrs.token_rotates_at - tp_now()).total_seconds()))

        return jsonify({
            "success": True,
            "token": token,
            "checkin_url": _checkin_url(token),
            "rotation_seconds": TOKEN_ROTATION_SECONDS,
            "token_seconds_left": token_seconds_left,
            "session_seconds_left": seconds_left,
            "expires_at": qrs.session_expires_at.isoformat(),
            "attendance_count": att_count,
            "qr_session_id": qrs.id,
            "attendance_session_id": qrs.attendance_session_id,
        })
    finally:
        db.close()


# ── Doctor: render QR PNG for the current token ─────────────────────────────
@qr_bp.route("/api/doctor/qr/image/<int:qr_session_id>", methods=["GET"])
@require_role("doctor", "dean")
def qr_image(qr_session_id):
    user = get_current_user()
    db = get_session()
    try:
        qrs = db.query(QRSession).filter_by(id=qr_session_id).first()
        if not qrs:
            return jsonify({"success": False, "error": "Not found"}), 404
        if user["role"] != "dean" and qrs.doctor_id != user.get("doctor_id"):
            return jsonify({"success": False, "error": "Forbidden"}), 403
        if not qrs.is_active or qrs.session_expires_at <= tp_now():
            return jsonify({"success": False, "error": "expired"}), 410
        token = _fresh_qr_session(qrs, db)
    finally:
        db.close()

    try:
        import qrcode
    except ImportError:
        return jsonify({"success": False, "error": "qrcode not installed"}), 500

    # خانة عالية الدقة + هامش واضح لقراءة موثوقة من بعيد
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=20,   # حجم كل خلية بكسل (كان ~10)
        border=4,
    )
    qr.add_data(_checkin_url(token))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png",
                     as_attachment=False,
                     download_name=f"qr_{qr_session_id}.png")


# ── Doctor: stop a QR session ───────────────────────────────────────────────
@qr_bp.route("/api/doctor/qr/stop/<int:qr_session_id>", methods=["POST"])
@require_role("doctor", "dean")
def qr_stop(qr_session_id):
    user = get_current_user()
    db = get_session()
    try:
        qrs = db.query(QRSession).filter_by(id=qr_session_id).first()
        if not qrs:
            return jsonify({"success": False, "error": "Not found"}), 404
        if user["role"] != "dean" and qrs.doctor_id != user.get("doctor_id"):
            return jsonify({"success": False, "error": "Forbidden"}), 403

        qrs.is_active = False
        db.commit()
        log_action("update", "qr_session", entity_id=qrs.id, entity_label="stopped")
        return jsonify({"success": True, "message": "QR session stopped"})
    finally:
        db.close()


# ── Public: student-facing check-in page (mobile) ───────────────────────────
_CHECKIN_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>تسجيل حضور</title>
<style>
  :root{--bg:#0f172a;--card:#1e293b;--accent:#8b5cf6;--ok:#10b981;--err:#ef4444;--muted:#94a3b8;--text:#f1f5f9}
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Tahoma,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:18px}
  .card{background:var(--card);padding:22px;border-radius:14px;max-width:380px;width:100%;box-shadow:0 8px 24px rgba(0,0,0,.4)}
  h1{font-size:20px;margin:0 0 4px;color:var(--accent)}
  .muted{color:var(--muted);font-size:13px;margin-bottom:18px}
  input{width:100%;padding:14px;font-size:17px;border-radius:10px;border:1px solid #334155;background:#0f172a;color:var(--text);margin-bottom:12px;direction:ltr;text-align:center}
  button{width:100%;padding:14px;font-size:16px;border-radius:10px;border:none;background:var(--accent);color:#fff;font-weight:bold;cursor:pointer}
  button:disabled{opacity:.5}
  .msg{margin-top:14px;padding:12px;border-radius:8px;font-size:14px;text-align:center;display:none}
  .msg.ok{background:rgba(16,185,129,.15);color:var(--ok);display:block}
  .msg.err{background:rgba(239,68,68,.15);color:var(--err);display:block}
  .info{background:#0f172a;border:1px solid #334155;padding:10px;border-radius:8px;font-size:13px;margin-bottom:14px}
</style></head>
<body><div class="card">
  <h1>تسجيل الحضور</h1>
  <div class="muted">امسح، أدخل الرقم الأكاديمي، أرسل.</div>
  <div class="info">
    المادة: <b>{{ course_name }}</b><br>
    الدكتور: <b>{{ doctor_name }}</b><br>
    {% if hall_name %}القاعة: <b>{{ hall_name }}</b><br>{% endif %}
    ينتهي: <b id="countdown">{{ seconds_left }}s</b>
  </div>
  <form id="f">
    <input type="text" name="academic_id" id="aid" placeholder="الرقم الأكاديمي" required inputmode="numeric" autocomplete="off">
    <button type="submit" id="btn">تسجيل الحضور</button>
  </form>
  <div class="msg" id="msg"></div>
</div>
<script>
  var token={{ token_js|safe }};
  var secs={{ seconds_left }};
  var cd=document.getElementById('countdown');
  setInterval(function(){if(secs>0){secs--;cd.textContent=secs+'s';}else{cd.textContent='منتهي';document.getElementById('btn').disabled=true;}},1000);
  document.getElementById('f').onsubmit=function(e){
    e.preventDefault();
    var aid=document.getElementById('aid').value.trim();
    var btn=document.getElementById('btn'),msg=document.getElementById('msg');
    if(!aid){return;}
    btn.disabled=true; btn.textContent='...جاري التسجيل';
    fetch('/qr/checkin/'+token,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({academic_id:aid})})
      .then(r=>r.json())
      .then(d=>{
        if(d.success){msg.className='msg ok';msg.textContent='✓ '+(d.message||'تم تسجيل الحضور: '+(d.student_name||''));}
        else{msg.className='msg err';msg.textContent='✗ '+(d.error||d.message||'فشل');btn.disabled=false;btn.textContent='إعادة المحاولة';}
      })
      .catch(err=>{msg.className='msg err';msg.textContent='✗ '+err;btn.disabled=false;btn.textContent='إعادة المحاولة';});
  };
</script></body></html>"""


@qr_bp.route("/qr/checkin/<token>", methods=["GET"])
def qr_checkin_page(token):
    db = get_session()
    try:
        qrs = db.query(QRSession).filter_by(current_token=token, is_active=True).first()
        if not qrs:
            return _simple_html("الرمز غير صالح أو انتهى", error=True), 404
        if qrs.session_expires_at <= tp_now():
            qrs.is_active = False
            db.commit()
            return _simple_html("انتهت جلسة الحضور", error=True), 410

        course = db.query(Course).filter_by(id=qrs.course_id).first() if qrs.course_id else None
        doctor = db.query(Doctor).filter_by(id=qrs.doctor_id).first()
        hall = db.query(Hall).filter_by(id=qrs.hall_id).first() if qrs.hall_id else None

        seconds_left = max(0, int((qrs.session_expires_at - tp_now()).total_seconds()))
        import json as _json
        return render_template_string(
            _CHECKIN_PAGE,
            course_name=(course.course_name if course else "—"),
            doctor_name=(doctor.full_name if doctor else "—"),
            hall_name=(hall.hall_name if hall else ""),
            token_js=_json.dumps(token),
            seconds_left=seconds_left,
        )
    finally:
        db.close()


def _simple_html(msg, error=False):
    color = "#ef4444" if error else "#10b981"
    return f"""<!DOCTYPE html><html dir=rtl><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>تسجيل حضور</title></head>
<body style="background:#0f172a;color:#f1f5f9;font-family:Tahoma,sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px">
<div style="background:#1e293b;padding:30px;border-radius:14px;max-width:380px;text-align:center">
<div style="font-size:48px;margin-bottom:10px;color:{color}">{'✗' if error else '✓'}</div>
<div style="font-size:18px;color:{color}">{msg}</div>
</div></body></html>"""


# ── Public: student submits check-in ────────────────────────────────────────
@qr_bp.route("/qr/checkin/<token>", methods=["POST"])
def qr_checkin_submit(token):
    data = request.get_json(silent=True) or {}
    academic_id = (data.get("academic_id") or "").strip()
    if not academic_id:
        return jsonify({"success": False, "error": "الرقم الأكاديمي مطلوب"}), 400

    db = get_session()
    try:
        qrs = db.query(QRSession).filter_by(current_token=token, is_active=True).first()
        if not qrs:
            return jsonify({"success": False, "error": "رمز QR منتهي أو غير صالح"}), 410
        if qrs.session_expires_at <= tp_now():
            qrs.is_active = False
            db.commit()
            return jsonify({"success": False, "error": "انتهت جلسة الحضور"}), 410

        student = db.query(Student).filter_by(academic_id=academic_id).first()
        if not student:
            return jsonify({"success": False, "error": "الطالب غير موجود"}), 404

        # تحقق من تسجيله في المادة
        if qrs.course_id:
            enr = db.query(Enrollment).filter_by(
                student_id=student.id, course_id=qrs.course_id).first()
            if not enr:
                return jsonify({"success": False,
                                "error": "غير مسجّل في هذه المادة"}), 403

        # تحقق من البطاقة المؤقتة المنتهية
        if student.is_temporary_card and student.card_expiry_date \
                and student.card_expiry_date < tp_today():
            return jsonify({"success": False, "error": "البطاقة المؤقتة منتهية"}), 403

        session_id = qrs.attendance_session_id
        student_id = student.id
        student_name = student.full_name
    finally:
        db.close()

    if check_duplicate_scan(session_id, student_id):
        return jsonify({"success": False,
                        "error": f"الطالب {student_name} مسجّل حضوره مسبقاً"}), 409

    rid, msg = record_attendance(session_id, student_id)
    if rid:
        return jsonify({"success": True,
                        "message": "تم تسجيل الحضور",
                        "student_name": student_name})
    return jsonify({"success": False, "error": msg or "فشل التسجيل"}), 500


# ── Doctor: list halls (helper for the QR start dialog) ─────────────────────
@qr_bp.route("/api/doctor/qr/halls", methods=["GET"])
@require_role("doctor", "dean")
def qr_halls():
    db = get_session()
    try:
        halls = db.query(Hall).all()
        return jsonify({"success": True,
                        "halls": [{"id": h.id, "hall_name": h.hall_name,
                                   "hall_type": h.hall_type} for h in halls]})
    finally:
        db.close()
