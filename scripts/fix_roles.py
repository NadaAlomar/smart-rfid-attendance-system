import glob

files = glob.glob("api/routes/*.py")
count = 0
for f in files:
    with open(f, "r", encoding="utf-8") as fh:
        content = fh.read()
    new_content = content.replace('@require_role("admin"', '@require_role("dean"')
    new_content = new_content.replace('@require_role("doctor", "admin")', '@require_role("doctor", "dean")')
    new_content = new_content.replace('role not in ("admin"', 'role not in ("dean"')
    new_content = new_content.replace('role in ("admin",)', 'role in ("dean",)')
    new_content = new_content.replace('current["role"] != "admin"', 'current["role"] != "dean"')
    new_content = new_content.replace('role == "admin"', 'role == "dean"')
    new_content = new_content.replace('.filter_by(role="admin")', '.filter_by(role="dean")')
    if new_content != content:
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(new_content)
        count += 1
        print(f"Updated: {f}")
    else:
        print(f"No changes: {f}")
print(f"\nTotal files updated: {count}")