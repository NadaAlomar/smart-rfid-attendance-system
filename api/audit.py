import json
from flask import request
from database import get_session
from database.models import AuditLog
from api.auth import get_current_user


def log_action(action, entity_type, entity_id=None, entity_label=None, changes=None):
    s = get_session()
    try:
        user = get_current_user()
        s.add(AuditLog(
            user_id=user["id"] if user else None,
            username=user["username"] if user else None,
            role=user["role"] if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_label=entity_label,
            changes_json=json.dumps(changes, ensure_ascii=False) if changes else None,
            ip_address=request.remote_addr if request else None,
        ))
        s.commit()
    except Exception:
        s.rollback()
    finally:
        s.close()