import json
import os
from pathlib import Path

_translations = {}
_missing_keys = set()

LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locales")
SUPPORTED_LANGS = ["ar", "en"]
_PREFS_FILE = Path(__file__).resolve().parent.parent / "data" / "ui_prefs.json"


def _read_saved_lang():
    """يقرأ اللغة المحفوظة من نفس ملف prefs الذي يستخدمه theme.py"""
    try:
        if _PREFS_FILE.exists():
            with open(_PREFS_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("lang", "ar")
    except Exception:
        pass
    return "ar"


_current_lang = _read_saved_lang()


def get_current_lang():
    return _current_lang


def set_lang(lang):
    global _current_lang
    if lang in SUPPORTED_LANGS:
        _current_lang = lang
        load_translations(lang)


def load_translations(lang=None):
    global _translations
    lang = lang or _current_lang
    path = os.path.join(LOCALES_DIR, f"{lang}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            _translations = json.load(f)
    else:
        _translations = {}


def t(key, default=None):
    val = _translations.get(key)
    if val:
        return val
    _missing_keys.add(key)
    if default:
        return default
    return key


def get_missing_keys():
    return sorted(_missing_keys)


def clear_missing_keys():
    _missing_keys.clear()


def t_lang(key):
    return t(key, key)


load_translations()