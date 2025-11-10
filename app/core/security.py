"""Simple password hashing helpers for database connection secrets."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Tuple

_HASH_DELIMITER = "$"


def _split_hash(hash_value: str) -> Tuple[str, str]:
    try:
        salt, digest = hash_value.split(_HASH_DELIMITER, 1)
    except ValueError:  # pragma: no cover - defensive fallback
        raise ValueError("Invalid hash format; expected '<salt>$<digest>'")
    return salt, digest


def get_password_hash(password: str, *, salt: str | None = None) -> str:
    """Hash a password with a random salt using SHA-256."""
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"{salt}{_HASH_DELIMITER}{digest}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify ``password`` against ``hashed_password``."""
    salt, digest = _split_hash(hashed_password)
    check = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return hmac.compare_digest(check, digest)


__all__ = ["get_password_hash", "verify_password"]
