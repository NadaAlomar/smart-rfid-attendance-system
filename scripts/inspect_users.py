import sys, io, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from database import get_session
from database.models import User, Doctor

s = get_session()
try:
    print("Users:")
    for u in s.query(User).all():
        link = ""
        if u.doctor:
            link = f"  -> doctor: {u.doctor.full_name}"
        print(f"  id={u.id}  role={u.role:15s}  username={u.username!r}{link}")
    print()
    print("Doctors:")
    for d in s.query(Doctor).all():
        has = "OK" if d.user_id else "NO_ACCOUNT"
        print(f"  id={d.id}  name={d.full_name!r}  user_id={d.user_id}  -> {has}")
finally:
    s.close()
