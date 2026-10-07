"""
add_device.py
==============
سكربت لإضافة جهاز RFID جديد (لقاعة محددة).

الاستخدام:
    python add_device.py
    
سيسألك عن:
  • معرّف الجهاز (مثل DEVICE002, HALL_A_SCANNER, ...)
  • القاعة (يعرض القائمة)
  
ثم يُولّد توكن جديد ويحفظه:
  • في قاعدة البيانات
  • في ملف data/<device_id>_token.txt (لنسخه للأردوينو)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_session
from database.models import Device, Hall
from security.security_manager import generate_device_token


def main():
    print("=" * 60)
    print("  إضافة جهاز RFID جديد")
    print("=" * 60)
    print()

    session = get_session()
    try:
        # عرض القاعات الموجودة
        halls = session.query(Hall).all()
        if not halls:
            print("[!] لا توجد قاعات. أضف قاعة من الواجهة أولاً.")
            return

        print("القاعات المتاحة:")
        for h in halls:
            print(f"  [{h.id}]  {h.hall_name}  ({h.hall_type})")
        print()

        # اختيار القاعة
        try:
            hall_id = int(input("ID القاعة: ").strip())
        except ValueError:
            print("[!] رقم غير صحيح.")
            return

        hall = session.query(Hall).filter_by(id=hall_id).first()
        if not hall:
            print("[!] القاعة غير موجودة.")
            return

        # تحقق إذا في جهاز موجود لهالقاعة
        existing = session.query(Device).filter_by(hall_id=hall_id).all()
        if existing:
            print(f"\n[!] القاعة '{hall.hall_name}' فيها أجهزة:")
            for d in existing:
                print(f"     - {d.device_id} (token: {d.device_token[:8]}...)")
            print()
            ans = input("هل تريد إضافة جهاز ثاني للقاعة نفسها؟ (y/N): ").strip().lower()
            if ans != "y":
                print("تم الإلغاء.")
                return

        # معرّف الجهاز
        device_id = input("\nمعرّف الجهاز (مثل DEVICE003): ").strip().upper()
        if not device_id:
            print("[!] معرّف الجهاز مطلوب.")
            return

        if session.query(Device).filter_by(device_id=device_id).first():
            print(f"[!] جهاز بمعرّف '{device_id}' موجود مسبقاً.")
            return

        # توليد توكن جديد
        token = generate_device_token()

        # حفظ في DB
        new_device = Device(
            device_id=device_id,
            hall_id=hall_id,
            device_token=token,
            is_active=True,
        )
        session.add(new_device)
        session.commit()

        # حفظ في ملف
        os.makedirs("data", exist_ok=True)
        token_file = f"data/{device_id}_token.txt"
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(f"device_id={device_id}\n")
            f.write(f"token={token}\n")
            f.write(f"hall_id={hall_id}\n")
            f.write(f"hall_name={hall.hall_name}\n")

        # عرض النتيجة
        print()
        print("=" * 60)
        print("  ✅  تم إنشاء الجهاز بنجاح!")
        print("=" * 60)
        print(f"  Device ID:   {device_id}")
        print(f"  Hall:        {hall.hall_name}")
        print(f"  Token:       {token}")
        print(f"  Saved to:    {token_file}")
        print()
        print("  انسخ القيم التالية إلى كود Arduino:")
        print(f'    #define DEVICE_ID  "{device_id}"')
        print()
        print("  التوكن سيُجلب تلقائياً من السيرفر عند أول تشغيل.")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"[!] خطأ: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
