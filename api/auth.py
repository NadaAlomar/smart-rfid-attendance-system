import secrets
from functools import wraps
from datetime import datetime, timedelta

from flask import request, jsonify, g
from database import get_session
from database.models import UserSession


SESSION_DURATION = timedelta(hours=12)


def generate_token():
    return secrets.token_urlsafe(48)


def get_current_user():
    if hasattr(g, "current_user"):
        return g.current_user
    token = request.headers.get("X-Session-Token", "")
    if not token:
        g.current_user = None
        return None
    s = get_session()
    try:
        sess = s.query(UserSession).filter_by(token=token).first()
        if not sess or sess.expires_at < datetime.utcnow():
            g.current_user = None
            return None
        sess.last_seen = datetime.utcnow()
        s.commit()
        user = sess.user
        g.current_user = {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "doctor_id": user.doctor.id if user.doctor else None,
        }
        return g.current_user
    finally:
        s.close()


def require_role(*allowed):
    normalized = set(allowed)
    def deco(fn):
        @wraps(fn)
        def inner(*args, **kw):
            user = get_current_user()
            if not user:
                return jsonify({"success": False, "error": "unauthorized"}), 401
            if user["role"] not in normalized:
                return jsonify({
                    "success": False,
                    "error": "forbidden",
                    "your_role": user["role"],
                }), 403
            return fn(*args, **kw)
        return inner
    return deco
