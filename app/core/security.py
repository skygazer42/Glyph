"""Password hashing for configured API accounts."""

from __future__ import annotations

import hashlib
import hmac
import os

_PBKDF2_ITERATIONS = 600_000


def get_password_hash(password: str, *, salt: str | None = None) -> str:
    """Hash a password with a random salt using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify ``password`` against ``hashed_password``."""
    algorithm, iterations, salt, digest = hashed_password.split("$")
    if algorithm != "pbkdf2_sha256":
        raise ValueError("Unsupported password hash algorithm")
    check = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
    ).hex()
    return hmac.compare_digest(check, digest)


__all__ = ["get_password_hash", "verify_password"]
