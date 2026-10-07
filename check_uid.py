import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from database import get_session
from database.models import Student, Doctor
from security.security_manager import hash_rfid_uid

s = get_session()

raw = "80831655"
hashed = hash_rfid_uid(raw)
print(f"Raw UID:  {raw}")
print(f"Hashed:   {hashed}")
print()

st = s.query(Student).filter_by(hashed_uid=hashed).first()
dr = s.query(Doctor).filter_by(hashed_uid=hashed).first()
print(f"Student match: {st.full_name if st else 'NONE'}")
print(f"Doctor match:  {dr.full_name if dr else 'NONE'}")
print()

print("All students:")
for x in s.query(Student).all():
    print(f"  id={x.id} name={x.full_name} hash={x.hashed_uid[:30]}...")

print("All doctors:")
for x in s.query(Doctor).all():
    print(f"  id={x.id} name={x.full_name} hash={x.hashed_uid[:30]}...")

s.close()
