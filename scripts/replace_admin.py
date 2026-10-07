import os, re

ROUTES_DIR = os.path.join(os.path.dirname(__file__), "..", "api", "routes")

files = [
    "dean_routes.py",
    "scanner_routes.py",
    "secretary_routes.py",
    "management_routes.py",
    "settings_routes.py",
    "doctor_portal_routes.py",
    "auth_routes.py",
]

for fname in files:
    path = os.path.join(ROUTES_DIR, fname)
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    
    content = content.replace('"admin", "dean"', '"dean"')
    content = content.replace('"admin", "dean_assistant"', '"dean", "dean_assistant"')
    
    remaining = re.findall(r'@require_role\([^)]*"admin"[^)]*\)', content)
    for m in remaining:
        fixed = m.replace('"admin", ', '').replace(', "admin"', '').replace('"admin"', '"dean"')
        if fixed == '@require_role()':
            fixed = '@require_role("dean")'
        content = content.replace(m, fixed)
    
    content = re.sub(r'\("admin",\s*', '("dean", ', content)
    content = re.sub(r',\s*"admin"\)', ', "dean")', content)
    
    content = content.replace('role not in ("admin", "dean", "dean_assistant", "secretary", "doctor")',
                             'role not in ("dean", "dean_assistant", "secretary", "doctor")')
    content = content.replace('role not in ("dean", "dean", "dean_assistant", "secretary", "doctor")',
                             'role not in ("dean", "dean_assistant", "secretary", "doctor")')
    
    content = content.replace('current["role"] != "admin" and role in ("admin",)',
                              'current["role"] != "dean" and role in ("admin",)')
    
    content = content.replace('if user.role == "admin":\n            admins = s.query(User).filter_by(role="admin").count()',
                              'if user.role == "dean":\n            deans = s.query(User).filter_by(role="dean").count()')
    
    if content != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        count = content.count('"dean"') - original.count('"dean"')
        print(f"Updated {fname}: replaced admin refs")
    else:
        print(f"No changes in {fname}")