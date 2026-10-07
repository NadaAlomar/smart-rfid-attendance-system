"""
Setup device token and update database
Run: python setup_device.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from security.security_manager import generate_device_token
from database import get_engine, get_session, Base
from database.models import Device, Hall


def setup():
    TOKEN_FILE = os.path.join("data", "device_token.txt")
    DEVICE_ID = "DEVICE001"

    # إذا في توكن محفوظ سابقاً — استخدمه، ما تولّد واحد جديد
    existing_token = None
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("token="):
                        existing_token = line.strip().split("=", 1)[1]
                        break
        except Exception:
            pass

    if existing_token and len(existing_token) >= 16:
        token = existing_token
        print(f"[TOKEN] التوكن محفوظ مسبقاً: {token}")
    else:
        if existing_token:
            print(f"[TOKEN] التوكن المحفوظ غير صالح ({existing_token}) — يتم توليد واحد جديد...")
        token = generate_device_token()
        print(f"[TOKEN] توكن جديد: {token}")

    # حفظ التوكن بملف
    os.makedirs("data", exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(f"device_id={DEVICE_ID}\n")
        f.write(f"token={token}\n")
    print(f"[FILE] تم حفظ التوكن في: {TOKEN_FILE}")

    # تحديث قاعدة البيانات
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    session = get_session()
    try:
        device = session.query(Device).filter_by(device_id=DEVICE_ID).first()
        if device:
            device.device_token = token
            device.is_active = True
            # تأكد إنه الجهاز مربوط بقاعة
            if device.hall_id is None:
                hall = session.query(Hall).first()
                if hall:
                    device.hall_id = hall.id
                    print(f"[DB] تم ربط {DEVICE_ID} بالقاعة: {hall.hall_name}")
            session.commit()
            print(f"[DB] تم تحديث توكن {DEVICE_ID} في قاعدة البيانات")
        else:
            hall = session.query(Hall).first()
            device = Device(
                device_id=DEVICE_ID,
                hall_id=hall.id if hall else None,
                device_token=token,
                is_active=True,
            )
            session.add(device)
            session.commit()
            print(f"[DB] تم إنشاء جهاز {DEVICE_ID} في قاعدة البيانات")
    except Exception as e:
        session.rollback()
        print(f"[DB] خطأ: {e}")
        raise
    finally:
        session.close()

    # طباعة التوكن للنسخ
    print("\n" + "=" * 50)
    print("  انسخ هذا التوكن لكود Arduino:")
    print(f"  {token}")
    print("=" * 50)

    return token


if __name__ == "__main__":
    setup()
