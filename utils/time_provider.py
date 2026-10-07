from datetime import datetime, timedelta

_override = {"offset_seconds": 0, "frozen_at": None}


def now():
    if _override["frozen_at"]:
        return _override["frozen_at"]
    base = datetime.now()
    return base + timedelta(seconds=_override["offset_seconds"])


def today():
    return now().date()


def set_offset(seconds):
    _override["offset_seconds"] = seconds
    _override["frozen_at"] = None


def freeze_at(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    _override["frozen_at"] = dt


def reset():
    _override["offset_seconds"] = 0
    _override["frozen_at"] = None


def is_overridden():
    return _override["offset_seconds"] != 0 or _override["frozen_at"] is not None
