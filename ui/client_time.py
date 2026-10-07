import threading
import time
from datetime import datetime, timedelta

import requests

import config


_lock = threading.Lock()
_offset = timedelta(0)
_frozen_at = None
_started = False


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def sync_now():
    global _offset, _frozen_at
    try:
        r = requests.get(f"{config.API_BASE}/api/time/current", timeout=3)
        data = r.json()
        if not data.get("success"):
            return
        mode = data.get("mode", "off")
        sim_dt = _parse_datetime(data.get("simulated_time"))
        real_dt = _parse_datetime(data.get("real_time"))
        with _lock:
            if mode == "freeze" and sim_dt:
                _frozen_at = sim_dt
                _offset = timedelta(0)
            elif mode == "offset" and sim_dt and real_dt:
                _frozen_at = None
                _offset = sim_dt - real_dt
            else:
                _frozen_at = None
                _offset = timedelta(0)
    except Exception:
        pass


def now():
    with _lock:
        frozen_at = _frozen_at
        offset = _offset
    if frozen_at is not None:
        return frozen_at
    return datetime.now() + offset


def start_sync_thread(interval=10):
    global _started
    if _started:
        return
    _started = True

    def loop():
        while True:
            sync_now()
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True).start()
