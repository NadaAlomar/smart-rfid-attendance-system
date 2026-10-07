import requests
import config

API_BASE = config.API_BASE
_session_token = ""
_session_expired_cb = None


def set_token(token):
    global _session_token
    _session_token = token


def get_token():
    return _session_token


def on_session_expired(cb):
    global _session_expired_cb
    _session_expired_cb = cb


def _headers():
    h = {}
    if _session_token:
        h["X-Session-Token"] = _session_token
    return h


def _check(r):
    if r.status_code == 401 and _session_expired_cb:
        try:
            _session_expired_cb()
        except Exception:
            pass
    return r


def api_get(path, **params):
    return _check(requests.get(f"{API_BASE}{path}", params=params, headers=_headers(), timeout=8))


def api_post(path, json_body=None):
    return _check(requests.post(f"{API_BASE}{path}", json=json_body, headers=_headers(), timeout=8))


def api_put(path, json_body=None):
    return _check(requests.put(f"{API_BASE}{path}", json=json_body, headers=_headers(), timeout=8))


def api_delete(path, **params):
    return _check(requests.delete(f"{API_BASE}{path}", params=params, headers=_headers(), timeout=8))


def api_post_file(path, files, data=None):
    return _check(requests.post(f"{API_BASE}{path}", files=files, data=data,
                                headers=_headers(), timeout=60))


def api_get_raw(path, **params):
    return _check(requests.get(f"{API_BASE}{path}", params=params, headers=_headers(),
                               timeout=30, stream=True))
