import hashlib
import secrets
import string
import hmac
from datetime import datetime


def hash_rfid_uid(uid: str) -> str:
    if not uid:
        raise ValueError("UID cannot be empty")
    return hashlib.sha256(uid.strip().upper().encode("utf-8")).hexdigest()


def verify_device_token(device_id: str, token: str, stored_token: str) -> bool:
    try:
        return hmac.compare_digest(token, stored_token)
    except Exception:
        return False


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")
    salt = secrets.token_hex(8)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, hashed = password_hash.split("$", 1)
        computed = hashlib.sha256((password + salt).encode()).hexdigest()
        return hmac.compare_digest(hashed, computed)
    except Exception:
        return False


def generate_device_token(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_secure_id(prefix: str = "") -> str:
    timestamp = int(datetime.now().timestamp())
    random_part = secrets.token_hex(8)
    return f"{prefix}{timestamp}{random_part}"
