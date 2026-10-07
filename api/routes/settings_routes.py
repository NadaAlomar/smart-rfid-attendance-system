"""Settings + time simulation endpoints."""
from flask import Blueprint, request, jsonify
from database import get_session
from database.models import Setting
from datetime import datetime
from utils import time_provider
from api.auth import require_role


settings_bp = Blueprint("settings", __name__)


SIM_KEYS = ("sim_time_mode", "sim_time_frozen_at", "sim_time_offset_seconds")


def _get_setting(session, key, default=""):
    s = session.query(Setting).filter_by(key=key).first()
    return s.value if s else default


def _set_setting(session, key, value, description=""):
    s = session.query(Setting).filter_by(key=key).first()
    if s:
        s.value = str(value)
    else:
        s = Setting(key=key, value=str(value), description=description)
        session.add(s)


@settings_bp.route("/api/settings/sim-time", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary")
def get_sim_time():
    session = get_session()
    try:
        mode = _get_setting(session, "sim_time_mode", "off")
        frozen_at = _get_setting(session, "sim_time_frozen_at", "")
        offset = _get_setting(session, "sim_time_offset_seconds", "0")
    finally:
        session.close()
    real = datetime.now()
    sim = time_provider.now()
    return jsonify({
        "success": True,
        "mode": mode,
        "frozen_at": frozen_at,
        "offset_seconds": int(offset) if offset.lstrip("-").isdigit() else 0,
        "real_time": real.isoformat(timespec="seconds"),
        "simulated_time": sim.isoformat(timespec="seconds"),
        "is_overridden": time_provider.is_overridden(),
    })


@settings_bp.route("/api/settings/sim-time", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def set_sim_time():
    data = request.get_json() or {}
    mode = (data.get("mode") or "off").strip().lower()
    if mode not in ("off", "freeze", "offset"):
        return jsonify({"success": False, "error": "mode must be off|freeze|offset"}), 400

    frozen_at_str = (data.get("frozen_at") or "").strip()
    offset_seconds = data.get("offset_seconds", 0)
    try:
        offset_seconds = int(offset_seconds)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "offset_seconds must be integer"}), 400

    # Apply on the live provider FIRST so we don't persist a state we couldn't apply
    if mode == "off":
        time_provider.reset()
    elif mode == "freeze":
        if not frozen_at_str:
            return jsonify({"success": False, "error": "frozen_at required when mode=freeze"}), 400
        try:
            dt = datetime.fromisoformat(frozen_at_str)
        except ValueError:
            return jsonify({"success": False, "error": "frozen_at: invalid ISO datetime"}), 400
        time_provider.freeze_at(dt)
    elif mode == "offset":
        time_provider.set_offset(offset_seconds)

    # Persist
    session = get_session()
    try:
        _set_setting(session, "sim_time_mode", mode, "Time simulation mode")
        _set_setting(session, "sim_time_frozen_at", frozen_at_str if mode == "freeze" else "")
        _set_setting(session, "sim_time_offset_seconds", offset_seconds if mode == "offset" else 0)
        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()

    restore_sim_time_from_db()

    # بعد تغيير الوقت: ولّد الجلسات المستحقّة حتى الوقت الجديد + أنشئ تنبيهات الغياب
    materialized = 0
    try:
        from api.controllers.attendance_controller import materialize_due_sessions
        materialized, _ = materialize_due_sessions()
    except Exception:
        materialized = 0

    return jsonify({
        "success": True,
        "mode": mode,
        "applied_at": time_provider.now().isoformat(timespec="seconds"),
        "materialized_sessions": materialized,
    })


@settings_bp.route("/api/settings/sim-time/reset", methods=["POST"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def reset_sim_time():
    time_provider.reset()
    session = get_session()
    try:
        _set_setting(session, "sim_time_mode", "off")
        _set_setting(session, "sim_time_frozen_at", "")
        _set_setting(session, "sim_time_offset_seconds", 0)
        session.commit()
    finally:
        session.close()
    restore_sim_time_from_db()
    return jsonify({"success": True})


@settings_bp.route("/api/time/current", methods=["GET"])
def get_current_time():
    try:
        session = get_session()
        try:
            mode = _get_setting(session, "sim_time_mode", "off")
        finally:
            session.close()
        real = datetime.now()
        sim = time_provider.now()
        return jsonify({
            "success": True,
            "real_time": real.isoformat(timespec="seconds"),
            "simulated_time": sim.isoformat(timespec="seconds"),
            "mode": mode,
            "is_overridden": time_provider.is_overridden(),
        })
    except Exception:
        real = datetime.now()
        return jsonify({
            "success": True,
            "real_time": real.isoformat(timespec="seconds"),
            "simulated_time": real.isoformat(timespec="seconds"),
            "mode": "off",
            "is_overridden": False,
        })


def restore_sim_time_from_db():
    """Read sim-time settings from DB and apply to time_provider.
    Called once at app startup so simulation persists across restarts."""
    try:
        session = get_session()
        try:
            mode = _get_setting(session, "sim_time_mode", "off")
            frozen_at = _get_setting(session, "sim_time_frozen_at", "")
            offset = _get_setting(session, "sim_time_offset_seconds", "0")
        finally:
            session.close()

        if mode == "freeze" and frozen_at:
            try:
                dt = datetime.fromisoformat(frozen_at)
                time_provider.freeze_at(dt)
            except ValueError:
                pass
        elif mode == "offset":
            try:
                time_provider.set_offset(int(offset))
            except (TypeError, ValueError):
                pass
        else:
            time_provider.reset()
    except Exception as e:
        print(f"[settings_routes] restore_sim_time_from_db failed: {e}")
