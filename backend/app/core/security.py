from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt

from app.core.config import settings
from app.core.errors import AppException

JWT_ALGORITHM = "HS256"
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt, enforcing the 72-byte limit."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        raise AppException(
            status_code=400,
            code="PASSWORD_TOO_LONG",
            message=f"Password must not exceed {MAX_PASSWORD_BYTES} bytes",
        )
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a bcrypt hash."""
    plain_bytes = plain_password.encode("utf-8")
    if len(plain_bytes) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(plain_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """Generates a signed JWT access token for the given user ID."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Decodes a JWT access token and returns the user ID, or raises AppException."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub: Optional[str] = payload.get("sub")
        if sub is None:
            raise AppException(
                status_code=401,
                code="INVALID_TOKEN",
                message="Could not validate credentials",
            )
        return int(sub)
    except jwt.ExpiredSignatureError:
        raise AppException(
            status_code=401,
            code="TOKEN_EXPIRED",
            message="Token has expired. Please log in again.",
        )
    except (jwt.PyJWTError, ValueError):
        raise AppException(
            status_code=401,
            code="INVALID_TOKEN",
            message="Could not validate credentials",
        )


from app.core.redact import redact

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "redact",
]

