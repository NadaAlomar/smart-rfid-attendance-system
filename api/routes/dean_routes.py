"""
Routes للعطل وتبرير الغياب
- العطل: قراءة للجميع، تعديل للمدير/العميدة
- تبرير الغياب: قراءة للجميع (سكرتارية تشاهد فقط)، تعديل للعميدة فقط
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, date
from sqlalchemy import or_
from database import get_session
from database.models import (
    Holiday, AbsenceJustification, Student, Course, User,
)
from api.auth import require_role, get_current_user
from api.audit import log_action

dean_bp = Blueprint("dean", __name__)


@dean_bp.route("/api/holidays", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def list_holidays():
    session = get_session()
    try:
        items = session.query(Holiday).order_by(Holiday.holiday_date.asc()).all()
        result = []
        for h in items:
            result.append({
                "id": h.id,
                "date": h.holiday_date.isoformat(),
                "name": h.holiday_name,
                "type": h.holiday_type,
                "notes": h.notes or "",
            })
        return jsonify({"success": True, "holidays": result})
    finally:
        session.close()


@dean_bp.route("/api/holidays", methods=["POST"])
@require_role("dean", "dean_assistant")
def add_holiday():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "بيانات مفقودة"}), 400

    name = str(data.get("name", "")).strip()
    h_type = str(data.get("type", "holiday")).strip()
    notes = str(data.get("notes", "")).strip()
    from_date = data.get("from_date")
    to_date = data.get("to_date") or from_date

    if not name or not from_date:
        return jsonify({"success": False, "error": "الاسم والتاريخ مطلوبان"}), 400

    try:
        d_from = datetime.strptime(from_date, "%Y-%m-%d").date()
        d_to = datetime.strptime(to_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"success": False, "error": "صيغة التاريخ غير صحيحة (YYYY-MM-DD)"}), 400

    if d_to < d_from:
        return jsonify({"success": False, "error": "تاريخ النهاية قبل البداية"}), 400

    session = get_session()
    try:
        added = 0
        skipped = 0
        cur = d_from
        from datetime import timedelta
        while cur <= d_to:
            existing = session.query(Holiday).filter_by(holiday_date=cur).first()
            if existing:
                skipped += 1
            else:
                session.add(Holiday(
                    holiday_date=cur,
                    holiday_name=name,
                    holiday_type=h_type,
                    notes=notes or None,
                ))
                added += 1
            cur += timedelta(days=1)
        session.commit()
        log_action("create", "holiday", entity_id=None, entity_label=name, changes={"from_date": from_date, "to_date": to_date, "type": h_type})
        return jsonify({"success": True,
                         "message": f"تمت إضافة {added} يوم(أيام). تم تخطي {skipped}.",
                         "added": added, "skipped": skipped})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@dean_bp.route("/api/holidays/<int:hid>", methods=["DELETE"])
@require_role("dean", "dean_assistant")
def delete_holiday(hid):
    session = get_session()
    try:
        h = session.query(Holiday).filter_by(id=hid).first()
        if not h:
            return jsonify({"success": False, "error": "غير موجود"}), 404
        saved_name = h.holiday_name
        session.delete(h)
        session.commit()
        log_action("delete", "holiday", entity_id=hid, entity_label=saved_name)
        return jsonify({"success": True, "message": "تم الحذف"})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@dean_bp.route("/api/justifications", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary")
def list_justifications():
    search = request.args.get("search", "").strip()

    session = get_session()
    try:
        q = session.query(AbsenceJustification).join(Student)
        if search:
            like = f"%{search}%"
            q = q.filter(Student.full_name.ilike(like))
        items = q.order_by(AbsenceJustification.created_at.desc()).all()

        result = []
        for j in items:
            student = session.query(Student).filter_by(id=j.student_id).first()
            course = None
            if j.course_id:
                course = session.query(Course).filter_by(id=j.course_id).first()
            creator = None
            if j.created_by:
                creator = session.query(User).filter_by(id=j.created_by).first()

            result.append({
                "id": j.id,
                "student_id": j.student_id,
                "student_name": student.full_name if student else "؟",
                "academic_id": student.academic_id if student else "",
                "course_id": j.course_id,
                "course_name": course.course_name if course else "كل المواد",
                "from_date": j.from_date.isoformat(),
                "to_date": j.to_date.isoformat(),
                "reason": j.reason,
                "created_by": creator.username if creator else "—",
                "created_at": j.created_at.isoformat() if j.created_at else "",
            })
        return jsonify({"success": True, "justifications": result})
    finally:
        session.close()


@dean_bp.route("/api/justifications", methods=["POST"])
@require_role("dean", "dean_assistant")
def add_justification():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "بيانات مفقودة"}), 400

    user = get_current_user()
    user_id = user["id"] if user else None

    student_id = data.get("student_id")
    course_id = data.get("course_id")
    from_date = data.get("from_date")
    to_date = data.get("to_date")
    reason = str(data.get("reason", "")).strip()

    if not student_id or not from_date or not to_date or not reason:
        return jsonify({"success": False,
                         "error": "كل الحقول مطلوبة (طالب، تاريخ من، تاريخ إلى، السبب)"}), 400

    try:
        d_from = datetime.strptime(from_date, "%Y-%m-%d").date()
        d_to = datetime.strptime(to_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"success": False, "error": "صيغة التاريخ خاطئة"}), 400

    if d_to < d_from:
        return jsonify({"success": False, "error": "تاريخ النهاية قبل البداية"}), 400

    session = get_session()
    try:
        student = session.query(Student).filter_by(id=student_id).first()
        if not student:
            return jsonify({"success": False, "error": "الطالب غير موجود"}), 404

        j = AbsenceJustification(
            student_id=student_id,
            course_id=course_id if course_id else None,
            from_date=d_from,
            to_date=d_to,
            reason=reason,
            created_by=user_id,
        )
        session.add(j)
        session.commit()
        log_action("create", "justification", entity_id=j.id, entity_label=reason[:100], changes={"student_id": student_id, "from": from_date, "to": to_date})
        return jsonify({"success": True, "message": "تمت إضافة التبرير", "id": j.id})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@dean_bp.route("/api/justifications/<int:jid>", methods=["DELETE"])
@require_role("dean", "dean_assistant")
def delete_justification(jid):
    session = get_session()
    try:
        j = session.query(AbsenceJustification).filter_by(id=jid).first()
        if not j:
            return jsonify({"success": False, "error": "غير موجود"}), 404
        saved_reason = j.reason
        session.delete(j)
        session.commit()
        log_action("delete", "justification", entity_id=jid, entity_label=saved_reason)
        return jsonify({"success": True, "message": "تم الحذف"})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@dean_bp.route("/api/students/search", methods=["GET"])
@require_role("dean", "dean_assistant", "secretary", "doctor")
def search_students():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"success": True, "students": []})

    session = get_session()
    try:
        like = f"%{q}%"
        students = session.query(Student).filter(
            or_(
                Student.full_name.ilike(like),
                Student.academic_id.ilike(like),
            )
        ).limit(20).all()
        return jsonify({
            "success": True,
            "students": [{
                "id": s.id,
                "academic_id": s.academic_id,
                "full_name": s.full_name,
            } for s in students]
        })
    finally:
        session.close()
