"""
Cryptographic security utilities for password hashing, JWT creation/validation, and login rate limiting.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

logger = logging.getLogger("app.auth.security")

# Secret key resolution: require explicit env var in production; fallback to dev secret in test/dev
JWT_SECRET_KEY = os.environ.get(
    "JWT_SECRET_KEY",
    "quant_engine_dev_secret_key_change_in_production_9f83a2b1c0d4e5",
)
JWT_ALGORITHM = "HS256"
DEFAULT_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
TOKEN_ISSUER = "quant-portfolio-engine"


def hash_password(password: str) -> str:
    """
    Computes a cryptographic bcrypt hash of the plain password using a random salt.
    """
    pw_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a stored bcrypt hash in constant time.
    """
    try:
        pw_bytes = plain_password.encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception as exc:
        logger.warning("Password verification encountered an error: %s", exc)
        return False


def create_access_token(
    subject: str,
    claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Creates a signed JWT access token containing subject (user_id), claims, and expiration.
    """
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=DEFAULT_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": subject,
        "iss": TOKEN_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if claims:
        payload.update(claims)

    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodes and validates a JWT token signature and expiration.
    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    return jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        issuer=TOKEN_ISSUER,
        options={"require": ["exp", "sub", "iat"]},
    )


class LoginRateLimiter:
    """
    In-memory, thread-safe rate limiter to mitigate brute-force authentication attempts.
    Locks out an IP or email identifier after MAX_FAILURES consecutive failed attempts.
    """

    MAX_FAILURES = 5
    LOCKOUT_SECONDS = 300  # 5 minutes

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Maps identifier -> list of failure timestamps
        self._failures: dict[str, list[float]] = {}

    def is_locked_out(self, identifier: str) -> bool:
        norm_id = identifier.strip().lower()
        now = time.monotonic()
        with self._lock:
            timestamps = self._failures.get(norm_id, [])
            # Purge timestamps outside the lockout window
            valid_timestamps = [t for t in timestamps if now - t < self.LOCKOUT_SECONDS]
            self._failures[norm_id] = valid_timestamps
            return len(valid_timestamps) >= self.MAX_FAILURES

    def record_failure(self, identifier: str) -> int:
        norm_id = identifier.strip().lower()
        now = time.monotonic()
        with self._lock:
            timestamps = self._failures.setdefault(norm_id, [])
            timestamps.append(now)
            # Retain only recent timestamps
            self._failures[norm_id] = [t for t in timestamps if now - t < self.LOCKOUT_SECONDS]
            return len(self._failures[norm_id])

    def reset(self, identifier: str) -> None:
        norm_id = identifier.strip().lower()
        with self._lock:
            self._failures.pop(norm_id, None)

    def clear_all(self) -> None:
        with self._lock:
            self._failures.clear()


rate_limiter = LoginRateLimiter()
