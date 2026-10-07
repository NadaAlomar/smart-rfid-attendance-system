from datetime import datetime, timedelta, time
import config
import time as _time

_settings_cache = {"value": None, "timestamp": 0}
_CACHE_TTL = 30

_time_format_cache = {"value": None, "timestamp": 0}


def _get_session_timeout_from_db():
    now = _time.time()
    if _settings_cache["value"] is not None and (now - _settings_cache["timestamp"]) < _CACHE_TTL:
        return _settings_cache["value"]
    try:
        from database import get_session
        from database.models import Setting
        session = get_session()
        try:
            s = session.query(Setting).filter_by(key="session_timeout_minutes").first()
            if s and s.value:
                val = int(s.value)
                _settings_cache["value"] = val
                _settings_cache["timestamp"] = now
                return val
        finally:
            session.close()
    except Exception:
        pass
    _settings_cache["value"] = config.SESSION_TIMEOUT_MINUTES
    _settings_cache["timestamp"] = now
    return config.SESSION_TIMEOUT_MINUTES


def _get_time_format():
    now = _time.time()
    if _time_format_cache["value"] is not None and (now - _time_format_cache["timestamp"]) < _CACHE_TTL:
        return _time_format_cache["value"]
    try:
        from database import get_session
        from database.models import Setting
        session = get_session()
        try:
            s = session.query(Setting).filter_by(key="time_format").first()
            val = s.value if s and s.value else "12h"
            _time_format_cache["value"] = val
            _time_format_cache["timestamp"] = now
            return val
        finally:
            session.close()
    except Exception:
        pass
    return "12h"


def format_time(dt_or_time, lang=None, fmt=None):
    if dt_or_time is None:
        return ""
    lang = lang or "ar"
    fmt = fmt or _get_time_format()

    if isinstance(dt_or_time, str):
        if "T" in dt_or_time:
            try:
                dt_or_time = datetime.fromisoformat(dt_or_time.replace("Z", ""))
            except Exception:
                return dt_or_time
        elif ":" in dt_or_time and len(dt_or_time) <= 8:
            try:
                parts = dt_or_time.split(":")
                h, m = int(parts[0]), int(parts[1])
                if fmt == "24h":
                    return f"{h:02d}:{m:02d}"
                ampm = "م" if lang == "ar" else "PM"
                period = "ص" if lang == "ar" else "AM"
                if h >= 12:
                    h12 = h - 12 if h > 12 else 12
                    suffix = ampm
                else:
                    h12 = h if h > 0 else 12
                    suffix = period
                return f"{h12:02d}:{m:02d} {suffix}"
            except Exception:
                return dt_or_time
        return dt_or_time

    if isinstance(dt_or_time, datetime):
        t = dt_or_time.time()
    elif isinstance(dt_or_time, time):
        t = dt_or_time
    else:
        return str(dt_or_time)

    h, m = t.hour, t.minute
    if fmt == "24h":
        return f"{h:02d}:{m:02d}"

    ampm = "م" if lang == "ar" else "PM"
    period = "ص" if lang == "ar" else "AM"
    if h >= 12:
        h12 = h - 12 if h > 12 else 12
        suffix = ampm
    else:
        h12 = h if h > 0 else 12
        suffix = period
    return f"{h12:02d}:{m:02d} {suffix}"


def get_current_week(start_date=None):
    if start_date is None:
        start_date = datetime(datetime.now().year, 9, 1)
    today = datetime.now().date()
    if isinstance(start_date, str):
        start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start = (
            start_date
            if isinstance(start_date, datetime)
            else datetime.combine(start_date, datetime.min.time())
        )
    days_diff = (today - start.date()).days
    week_number = (days_diff // 7) + 1
    return max(1, week_number) if days_diff >= 0 else 1


def is_within_schedule(current_time, start_time, end_time):
    if isinstance(current_time, str):
        current_time = datetime.strptime(current_time, "%H:%M").time()
    if isinstance(start_time, str):
        start_time = datetime.strptime(start_time, "%H:%M").time()
    if isinstance(end_time, str):
        end_time = datetime.strptime(end_time, "%H:%M").time()
    return start_time <= current_time <= end_time


def get_day_of_week(date=None):
    if date is None:
        return datetime.now().weekday()
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")
    return date.weekday()


def calculate_session_duration(start_timestamp, end_timestamp=None):
    if end_timestamp is None:
        end_timestamp = datetime.now()
    duration = end_timestamp - start_timestamp
    return duration.total_seconds() / 60


def is_session_expired(start_timestamp, timeout_minutes=None):
    if timeout_minutes is None:
        timeout_minutes = _get_session_timeout_from_db()
    elapsed = datetime.now() - start_timestamp
    return elapsed.total_seconds() >= timeout_minutes * 60


def format_time_for_display(time_obj):
    if isinstance(time_obj, time):
        return time_obj.strftime("%I:%M %p")
    return str(time_obj)


def get_date_range_for_week(week_number, year=None, start_date=None):
    if year is None:
        year = datetime.now().year
    if start_date is None:
        start_date = datetime(year, 9, 1)
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
    week_start = start_date + timedelta(weeks=week_number - 1)
    week_end = week_start + timedelta(days=6)
    return week_start.date(), week_end.date()