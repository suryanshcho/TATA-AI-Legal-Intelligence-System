import hashlib
import hmac
import time
from datetime import datetime, timedelta

from backend.config import settings

PEPPER = "tata-legal"


def hash_password(password: str) -> str:
    return hashlib.sha256(f"{PEPPER}:{password}".encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def make_token(user_id: int, email: str, role: str) -> str:
    payload = f"{user_id}:{email}:{role}:{int(time.time()) + settings.TOKEN_TTL_HOURS * 3600}"
    sig = hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def parse_token(token: str):
    try:
        body, sig = token.rsplit(".", 1)
        expect = hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, sig):
            return None
        user_id, email, role, exp = body.split(":")
        if int(exp) < int(time.time()):
            return None
        return {"user_id": int(user_id), "email": email, "role": role}
    except Exception:
        return None


def now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def days_from_now(days: int) -> str:
    return (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
