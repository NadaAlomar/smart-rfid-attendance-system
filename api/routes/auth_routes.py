from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta

from database import get_session
from database.models import User, UserSession
from security.security_manager import verify_password, hash_password
from api.auth import generate_token, get_current_user, SESSION_DURATION, require_role
from api.audit import log_action

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"}), 400

    s = get_session()
    try:
        user = s.query(User).filter_by(username=username).first()
        if not user or not verify_password(password, user.password_hash):
            return jsonify({"success": False, "error": "invalid_credentials"}), 401

        for old in s.query(UserSession).filter_by(user_id=user.id).all():
            s.delete(old)
        s.flush()

        token = generate_token()
        sess = UserSession(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + SESSION_DURATION,
        )
        s.add(sess)
        s.commit()

        return jsonify({
            "success": True,
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "doctor_id": user.doctor.id if user.doctor else None,
            },
        })
    except Exception as e:
        s.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        s.close()


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    user = get_current_user()
    if not user:
        return jsonify({"success": True})
    token = request.headers.get("X-Session-Token", "")
    s = get_session()
    try:
        sess = s.query(UserSession).filter_by(token=token).first()
        if sess:
            s.delete(sess)
            s.commit()
        return jsonify({"success": True})
    finally:
        s.close()


@auth_bp.route("/api/auth/me", methods=["GET"])
def me():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "unauthorized"}), 401
    return jsonify({"success": True, "user": user})


@auth_bp.route("/api/auth/refresh", methods=["POST"])
def refresh_session():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "unauthorized"}), 401
    token = request.headers.get("X-Session-Token", "")
    s = get_session()
    try:
        sess = s.query(UserSession).filter_by(token=token).first()
        if sess:
            sess.expires_at = datetime.utcnow() + SESSION_DURATION
            s.commit()
        return jsonify({"success": True})
    finally:
        s.close()


@auth_bp.route("/api/auth/accounts", methods=["GET"])
@require_role("dean")
def list_accounts():
    s = get_session()
    try:
        users = s.query(User).all()
        return jsonify({
            "success": True,
            "accounts": [{
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "doctor_id": u.doctor.id if u.doctor else None,
                "doctor_name": u.doctor.full_name if u.doctor else None,
            } for u in users],
        })
    finally:
        s.close()


@auth_bp.route("/api/auth/accounts", methods=["POST"])
@require_role("dean")
def create_account():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = (data.get("role") or "").strip()
    doctor_id = data.get("doctor_id")

    if not username or not password or not role:
        return jsonify({"success": False, "error": "All fields required"}), 400
    if role not in ("dean", "dean_assistant", "secretary", "doctor"):
        return jsonify({"success": False, "error": "Invalid role"}), 400

    current = get_current_user()
    if current["role"] != "dean" and role in ("dean",):
        return jsonify({"success": False, "error": "forbidden"}), 403

    s = get_session()
    try:
        if s.query(User).filter_by(username=username).first():
            return jsonify({"success": False, "error": "Username already exists"}), 400
        user = User(
            username=username,
            password_hash=hash_password(password),
            role=role,
        )
        if doctor_id and role == "doctor":
            user.doctor_id_proxy = doctor_id
        s.add(user)
        s.flush()
        if doctor_id and role == "doctor":
            from database.models import Doctor
            doc = s.query(Doctor).filter_by(id=doctor_id).first()
            if doc:
                doc.user_id = user.id
        s.commit()
        return jsonify({"success": True, "id": user.id})
    except Exception as e:
        s.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        s.close()


@auth_bp.route("/api/auth/accounts/<int:uid>/password", methods=["PUT"])
@require_role("dean")
def reset_password(uid):
    """يعيد ضبط كلمة مرور حساب — للعميدة فقط."""
    data = request.get_json() or {}
    new_password = data.get("password") or ""
    if not new_password or len(new_password) < 4:
        return jsonify({"success": False,
                        "error": "كلمة المرور مطلوبة (4 أحرف على الأقل)"}), 400
    s = get_session()
    try:
        user = s.query(User).filter_by(id=uid).first()
        if not user:
            return jsonify({"success": False, "error": "الحساب غير موجود"}), 404
        user.password_hash = hash_password(new_password)
        # أبطل الجلسات الحالية للمستخدم — يلزم تسجيل دخول جديد
        for sess in s.query(UserSession).filter_by(user_id=uid).all():
            s.delete(sess)
        s.commit()
        log_action("update", "account", entity_id=uid,
                   entity_label=f"password reset ({user.username})")
        return jsonify({"success": True, "message": "تم تحديث كلمة المرور"})
    except Exception as e:
        s.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        s.close()


@auth_bp.route("/api/auth/accounts/<int:uid>/username", methods=["PUT"])
@require_role("dean")
def change_username(uid):
    """تغيير اسم المستخدم — للعميدة فقط."""
    data = request.get_json() or {}
    new_username = (data.get("username") or "").strip()
    if not new_username:
        return jsonify({"success": False, "error": "اسم المستخدم مطلوب"}), 400
    s = get_session()
    try:
        user = s.query(User).filter_by(id=uid).first()
        if not user:
            return jsonify({"success": False, "error": "الحساب غير موجود"}), 404
        clash = s.query(User).filter(User.username == new_username,
                                      User.id != uid).first()
        if clash:
            return jsonify({"success": False,
                            "error": "اسم المستخدم مستخدم من قبل حساب آخر"}), 400
        old_name = user.username
        user.username = new_username
        s.commit()
        log_action("update", "account", entity_id=uid,
                   entity_label=f"username: {old_name} -> {new_username}")
        return jsonify({"success": True, "message": "تم تغيير اسم المستخدم"})
    except Exception as e:
        s.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        s.close()


@auth_bp.route("/api/auth/accounts/<int:uid>", methods=["DELETE"])
@require_role("dean")
def delete_account(uid):
    s = get_session()
    try:
        user = s.query(User).filter_by(id=uid).first()
        if not user:
            return jsonify({"success": False, "error": "Not found"}), 404
        if user.role == "dean":
            deans = s.query(User).filter_by(role="dean").count()
            if deans <= 1:
                return jsonify({"success": False, "error": "Cannot delete last dean"}), 400
        saved_username = user.username
        for sess in s.query(UserSession).filter_by(user_id=uid).all():
            s.delete(sess)
        s.delete(user)
        s.commit()
        log_action("delete", "account", entity_id=uid, entity_label=saved_username)
        return jsonify({"success": True})
    except Exception as e:
        s.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        s.close()
