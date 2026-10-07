import json
import sys
import os

locales_dir = os.path.join(os.path.dirname(__file__), "..", "ui", "locales")

with open(os.path.join(locales_dir, "ar.json"), encoding="utf-8") as f:
    ar = set(json.load(f).keys())
with open(os.path.join(locales_dir, "en.json"), encoding="utf-8") as f:
    en = set(json.load(f).keys())

missing_in_en = ar - en
missing_in_ar = en - ar

if missing_in_en:
    print(f"Missing from en.json: {sorted(missing_in_en)}")
if missing_in_ar:
    print(f"Missing from ar.json: {sorted(missing_in_ar)}")
if not missing_in_ar and not missing_in_en:
    print("Translations are in sync")
    sys.exit(0)
else:
    sys.exit(1)
