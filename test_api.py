"""End-to-end API test"""
import requests
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:5000"
TOKEN = os.environ.get("TEST_DEVICE_TOKEN", "")
errors = 0

print("=== END-TO-END TEST ===\n")

# 1
r = requests.get(f"{BASE}/")
s = r.json().get("status")
ok = r.status_code == 200 and s == "running"
print(f"[{'OK' if ok else 'FAIL'}] GET /             -> {r.status_code} : {s}")
if not ok: errors += 1

# 2
r = requests.get(f"{BASE}/api/status")
s = r.json().get("status")
ok = r.status_code == 200 and s == "online"
print(f"[{'OK' if ok else 'FAIL'}] GET /api/status   -> {r.status_code} : {s}")
if not ok: errors += 1

# 3 - Valid token, unknown card = 404
r = requests.post(f"{BASE}/api/scan", json={"uid": "17D64A52", "device_id": "DEVICE001", "device_token": TOKEN})
ok = r.status_code == 404 and r.json().get("error") == "unknown_card"
print(f"[{'OK' if ok else 'FAIL'}] POST /api/scan (valid token, unknown card) -> {r.status_code} : {r.json().get('error')}")
if not ok: errors += 1

# 4 - Bad token = 401
r = requests.post(f"{BASE}/api/scan", json={"uid": "17D64A52", "device_id": "DEVICE001", "device_token": "WRONG"})
ok = r.status_code == 401 and r.json().get("error") == "unauthorized_device"
print(f"[{'OK' if ok else 'FAIL'}] POST /api/scan (bad token)    -> {r.status_code} : {r.json().get('error')}")
if not ok: errors += 1

# 5 - Missing fields = 400
r = requests.post(f"{BASE}/api/scan", json={"uid": "17D64A52"})
ok = r.status_code == 400 and r.json().get("error") == "Missing required fields"
print(f"[{'OK' if ok else 'FAIL'}] POST /api/scan (no token)     -> {r.status_code} : {r.json().get('error')}")
if not ok: errors += 1

# 6 - Same via WiFi IP
r = r = requests.post("http://127.0.0.1:5000/api/scan", json={"uid": "17D64A52", "device_id": "DEVICE001", "device_token": TOKEN}, timeout=5)
ok = r.status_code == 404
print(f"[{'OK' if ok else 'FAIL'}] POST via local server -> {r.status_code} : {r.json().get('error')}")
if not ok: errors += 1

print(f"\n{'='*40}")
if errors == 0:
    print("  ALL 6 TESTS PASSED!")
else:
    print(f"  {errors} TEST(S) FAILED")
print(f"{'='*40}")
