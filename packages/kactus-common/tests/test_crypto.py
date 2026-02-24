"""Tests for kactus_common.crypto — Fernet encryption + bcrypt password hashing."""

import pytest
from kactus_common.crypto import CryptoService, hash_password, verify_password


class TestCryptoService:
    """Fernet-based symmetric encryption."""

    def setup_method(self):
        self.key = CryptoService.generate_key()
        self.crypto = CryptoService(self.key)

    def test_encrypt_decrypt_roundtrip(self):
        original = "hello-secret-world"
        encrypted = self.crypto.encrypt(original)
        assert encrypted != original
        assert self.crypto.decrypt(encrypted) == original

    def test_encrypt_produces_different_tokens(self):
        """Fernet tokens include a timestamp, so same input → different output."""
        a = self.crypto.encrypt("same")
        b = self.crypto.encrypt("same")
        assert a != b

    def test_decrypt_with_wrong_key_fails(self):
        other = CryptoService(CryptoService.generate_key())
        encrypted = self.crypto.encrypt("secret")
        with pytest.raises(Exception):
            other.decrypt(encrypted)

    def test_empty_string(self):
        encrypted = self.crypto.encrypt("")
        assert self.crypto.decrypt(encrypted) == ""

    def test_unicode_data(self):
        original = "こんにちは世界 🌍"
        encrypted = self.crypto.encrypt(original)
        assert self.crypto.decrypt(encrypted) == original

    def test_generate_key_returns_valid_key(self):
        key = CryptoService.generate_key()
        assert isinstance(key, str)
        assert len(key) > 0
        # Should be usable to instantiate a CryptoService
        CryptoService(key)


class TestPasswordHashing:
    """bcrypt password hashing (one-way)."""

    def test_hash_and_verify(self):
        password = "MyS3cur3P@ss!"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """bcrypt uses random salt, so same password → different hash."""
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2
        assert verify_password("same-password", h1) is True
        assert verify_password("same-password", h2) is True

    def test_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("not-empty", hashed) is False
