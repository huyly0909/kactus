"""Encryption utilities — Fernet for reversible encryption, bcrypt for passwords."""

from __future__ import annotations

import bcrypt
from cryptography.fernet import Fernet


class CryptoService:
    """Fernet-based symmetric encryption for reversible data.

    Use for API keys, sensitive config values, etc.
    Do **NOT** use for passwords — use ``hash_password`` / ``verify_password`` instead.

    Usage::

        from kactus_common.crypto import CryptoService

        crypto = CryptoService(key=settings.encryption_key)
        encrypted = crypto.encrypt("secret-value")
        original = crypto.decrypt(encrypted)
    """

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, data: str) -> str:
        """Encrypt a string and return a URL-safe base64-encoded token."""
        return self._fernet.encrypt(data.encode()).decode()

    def decrypt(self, token: str) -> str:
        """Decrypt a Fernet token back to the original string."""
        return self._fernet.decrypt(token.encode()).decode()

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key (use once, store in env)."""
        return Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# Password hashing (bcrypt — one-way, irreversible)
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash a password with bcrypt. Returns the hash as a string."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())
