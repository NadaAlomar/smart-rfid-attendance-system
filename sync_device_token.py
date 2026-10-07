import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_session, init_db
from database.models import Device
from security.security_manager import generate_device_token


def sync_token(device_id=None, set_token=None):
    session = get_session()
    try:
        if device_id:
            device = session.query(Device).filter_by(device_id=device_id).first()
            if not device:
                print(f"[ERROR] الجهاز '{device_id}' غير موجود في قاعدة البيانات.")
                return
            devices = [device]
        else:
            devices = session.query(Device).all()

        if not devices:
            print("[INFO] لا توجد أجهزة مسجلة في قاعدة البيانات.")
            print("       سجّل جهازاً من واجهة النظام أولاً (إدارة القاعات).")
            return

        print("=" * 55)
        print("  مزامنة توكن الأجهزة")
        print("=" * 55)

        for device in devices:
            if set_token:
                new_token = set_token
            else:
                new_token = generate_device_token(32)

            old_token = device.device_token
            device.device_token = new_token
            device.is_active = True
            session.commit()

            print(f"\n  الجهاز:  {device.device_id}")
            print(f"  القاعة:  {device.hall_id}")
            print(f"  التوكن القديم: {old_token}")
            print(f"  التوكن الجديد: {new_token}")
            print(f"  ─────────────────────────────────────")
            print(f"  ↑ انسخ التوكن الجديد وضعه في كود Arduino:")
            print(f'  #define DEVICE_TOKEN   "{new_token}"')

        token_path = os.path.join(os.path.dirname(__file__), "data", "device_token.txt")
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, "w") as f:
            for device in devices:
                f.write(f"{device.device_id}={device.device_token}\n")
        print(f"\n  [OK] تم حفظ التوكنات في: {token_path}")

    except Exception as e:
        session.rollback()
        print(f"[ERROR] {e}")
    finally:
        session.close()


if __name__ == "__main__":
    init_db()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--device" and len(sys.argv) > 2:
            device_id = sys.argv[2]
            set_token = sys.argv[3] if len(sys.argv) > 3 else None
            sync_token(device_id=device_id, set_token=set_token)
        elif cmd == "--set" and len(sys.argv) > 2:
            sync_token(set_token=sys.argv[2])
        else:
            print("الاستخدام:")
            print("  python sync_device_token.py                     # توليد توكن جديد لكل الأجهزة")
            print("  python sync_device_token.py --device DEVICE001  # توليد لجهاز محدد")
            print("  python sync_device_token.py --set 01            # تعيين توكن محدد لكل الأجهزة")
    else:
        sync_token()