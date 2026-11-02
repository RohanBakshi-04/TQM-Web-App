"""Security, Password Hashing, and JWT Cryptographic Engine.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import bcrypt
import jwt
from backend.app.config import settings

# JWT Cryptographic Parameters sourced consistently from centralized settings
JWT_ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    """Return the centralized cryptographic secret key."""
    return settings.jwt_secret_key or settings.secret_key


def get_access_token_expire_minutes() -> int:
    """Return the configured access token expiration duration in minutes."""
    return settings.access_token_expire_minutes


def get_refresh_token_expire_days() -> int:
    """Return the configured refresh token expiration duration in days."""
    return settings.refresh_token_expire_days


# Backward-compatible property aliases
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.refresh_token_expire_days


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with salt rounds."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a short-lived signed JWT access token."""
    to_encode = data.copy()
    expire_minutes = get_access_token_expire_minutes()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=expire_minutes))
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    return jwt.encode(to_encode, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    """Generate a high-entropy random refresh token, its SHA-256 hash, and expiration timestamp."""
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=get_refresh_token_expire_days())
    return raw_token, token_hash, expires_at


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and cryptographically verify a JWT access token."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except (jwt.PyJWTError, Exception):
        return None
