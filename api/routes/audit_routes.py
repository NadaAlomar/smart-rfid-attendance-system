from flask import Blueprint, request, jsonify
from database import get_session
from database.models import AuditLog
from api.auth import require_role
from sqlalchemy import desc

audit_bp = Blueprint("audit", __name__)


@audit_bp.route("/api/audit-logs", methods=["GET"])
@require_role("dean", "dean_assistant")
def get_audit_logs():
    page = request.args.get("page", 1, type=int)
    per_page = min(200, max(10, request.args.get("per_page", 50, type=int)))
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    action = request.args.get("action")
    entity_type = request.args.get("entity_type")
    username = request.args.get("username")

    session = get_session()
    try:
        q = session.query(AuditLog)
        if from_date:
            from datetime import datetime as dt
            try:
                fd = dt.strptime(from_date, "%Y-%m-%d")
                q = q.filter(AuditLog.timestamp >= fd)
            except ValueError:
                pass
        if to_date:
            from datetime import datetime as dt
            try:
                td = dt.strptime(to_date, "%Y-%m-%d")
                q = q.filter(AuditLog.timestamp < td)
            except ValueError:
                pass
        if action:
            q = q.filter(AuditLog.action == action)
        if entity_type:
            q = q.filter(AuditLog.entity_type == entity_type)
        if username:
            q = q.filter(AuditLog.username.ilike(f"%{username}%"))

        total = q.count()
        logs = q.order_by(desc(AuditLog.timestamp)).offset((page - 1) * per_page).limit(per_page).all()

        result = []
        for log in logs:
            result.append({
                "id": log.id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "user_id": log.user_id,
                "username": log.username,
                "role": log.role,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "entity_label": log.entity_label,
                "changes_json": log.changes_json,
                "ip_address": log.ip_address,
            })
        return jsonify({
            "success": True,
            "logs": result,
            "total": total,
            "page": page,
            "per_page": per_page,
        })
    finally:
        session.close()