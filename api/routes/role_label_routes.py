from flask import Blueprint, request, jsonify
from database import get_session
from database.models import RoleLabel
from api.auth import require_role

role_labels_bp = Blueprint("role_labels", __name__)


@role_labels_bp.route("/api/role-labels", methods=["GET"])
def get_role_labels():
    session = get_session()
    try:
        labels = session.query(RoleLabel).all()
        return jsonify({
            "success": True,
            "labels": [{
                "role_key": l.role_key,
                "label_ar": l.label_ar,
                "label_en": l.label_en,
            } for l in labels],
        })
    finally:
        session.close()


@role_labels_bp.route("/api/role-labels/<string:key>", methods=["PUT"])
@require_role("dean")
def update_role_label(key):
    data = request.get_json() or {}
    session = get_session()
    try:
        label = session.query(RoleLabel).filter_by(role_key=key).first()
        if not label:
            label = RoleLabel(role_key=key)
            session.add(label)
        if "label_ar" in data:
            label.label_ar = data["label_ar"]
        if "label_en" in data:
            label.label_en = data["label_en"]
        session.commit()
        return jsonify({"success": True, "message": f"Role label '{key}' updated"})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()