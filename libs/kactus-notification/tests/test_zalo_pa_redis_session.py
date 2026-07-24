"""Tests for the Redis-backed Zalo QR session store.

The in-memory backend is covered in ``test_notification_zalo_pa.py``; this file
is about what changes when sessions move to Redis so several workers can serve
one login: cross-worker visibility, TTL expiry, and — the one that matters —
that the credentials are ciphertext at rest.

``fakeredis`` stands in for the server (no Docker); the encryption is real
Fernet, so the "not stored in the clear" assertion is meaningful.
"""

from __future__ import annotations

import fakeredis.aioredis
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from kactus_common.config import CommonSettings, clear_settings, register_settings
from kactus_common.exceptions import ConfigurationError
from kactus_notification import zalo_pa
from kactus_notification.config import NotificationSettings
from kactus_notification.zalo_pa import RedisZaloPASessionStore

TEST_KEY = Fernet.generate_key().decode()

CREDENTIALS = {
    "complete": True,
    "credentials": {
        "cookies": {"zpdid": "super-secret-cookie"},
        "imei": "device-imei",
        "zpw_sek": "sek-value",
        "zpsid": "zpsid-value",
        "secret_key": "secret-key-value",
        "user_agent": "ua",
    },
    "zalo_user_id": "u1",
    "account_name": "Me",
}


class _Settings(CommonSettings, NotificationSettings):
    """Composite settings, mirroring how kactus-fin merges the two branches."""


@pytest_asyncio.fixture
async def redis(monkeypatch):
    register_settings(_Settings(encryption_key=TEST_KEY, coordination_backend="redis"))
    server = fakeredis.aioredis.FakeRedis()
    monkeypatch.setattr(zalo_pa, "get_redis", lambda: server)
    yield server
    await server.flushall()
    await server.aclose()
    zalo_pa.reset_session_store()
    clear_settings()


def test_backend_selected_from_settings(redis):
    assert isinstance(zalo_pa.get_session_store(), RedisZaloPASessionStore)


@pytest.mark.asyncio
async def test_session_visible_to_another_worker(redis):
    """Two stores over one Redis == two workers. Step 1 on A, step 2 on B."""
    worker_a = RedisZaloPASessionStore()
    worker_b = RedisZaloPASessionStore()

    await worker_a.save("sid", CREDENTIALS, 300)
    assert await worker_b.load("sid") == CREDENTIALS


@pytest.mark.asyncio
async def test_credentials_are_ciphertext_at_rest(redis):
    """The stored blob must not contain the cookies, sek or sid in the clear."""
    store = RedisZaloPASessionStore()
    await store.save("sid", CREDENTIALS, 300)

    raw = await redis.get(store._key("sid"))
    assert raw is not None
    text = raw.decode()
    for secret in ("super-secret-cookie", "sek-value", "zpsid-value", "device-imei"):
        assert secret not in text
    # …and it still decrypts back to the original.
    assert await store.load("sid") == CREDENTIALS


@pytest.mark.asyncio
async def test_ttl_is_set_and_expiry_reads_as_absent(redis):
    store = RedisZaloPASessionStore()
    await store.save("sid", CREDENTIALS, 300)
    assert 0 < await redis.ttl(store._key("sid")) <= 300

    await redis.delete(store._key("sid"))  # stand-in for the TTL elapsing
    assert await store.load("sid") is None


@pytest.mark.asyncio
async def test_delete_removes_the_session(redis):
    store = RedisZaloPASessionStore()
    await store.save("sid", CREDENTIALS, 300)
    await store.delete("sid")
    assert await store.load("sid") is None
    assert await store.count() == 0


@pytest.mark.asyncio
async def test_count_sees_sessions_from_every_worker(redis):
    """``zalo_pa_max_sessions`` must cap the fleet, not one worker's share."""
    worker_a, worker_b = RedisZaloPASessionStore(), RedisZaloPASessionStore()
    await worker_a.save("s1", CREDENTIALS, 300)
    await worker_b.save("s2", CREDENTIALS, 300)
    assert await worker_a.count() == 2


@pytest.mark.asyncio
async def test_unreadable_session_is_dropped_not_raised(redis):
    """After a key rotation the blob cannot be decrypted.

    The user should land back at step 1, not on a 500 halfway through a login.
    """
    store = RedisZaloPASessionStore()
    await store.save("sid", CREDENTIALS, 300)

    rotated = RedisZaloPASessionStore()
    rotated._crypto = None
    register_settings(
        _Settings(
            encryption_key=Fernet.generate_key().decode(), coordination_backend="redis"
        )
    )

    assert await rotated.load("sid") is None
    assert await redis.get(store._key("sid")) is None  # and the junk is cleaned up


@pytest.mark.asyncio
async def test_redis_backend_requires_an_encryption_key(redis):
    """Refuse to write credentials in the clear rather than silently doing it."""
    register_settings(_Settings(encryption_key="", coordination_backend="redis"))
    store = RedisZaloPASessionStore()
    with pytest.raises(ConfigurationError):
        await store.save("sid", CREDENTIALS, 300)
