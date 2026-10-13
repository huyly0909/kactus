"""TTL session store for the 5-step Zalo QR login.

There is no DB row until the user picks a recipient and creates a channel, so
the half-finished login lives here. In memory that means all five steps must
land on the same worker; on Redis any worker can serve any step.

The interface is async because the Redis backend is — the in-memory one gains
nothing from it, but a sync interface would force the Redis one to block the
event loop, and every caller is already inside an async endpoint.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import orjson
from cryptography.fernet import InvalidToken
from kactus_common.config import settings
from kactus_common.crypto import CryptoService
from kactus_common.exceptions import ConfigurationError
from kactus_common.redis.client import get_redis, namespaced
from loguru import logger


@dataclass
class _Session:
    state: dict = field(default_factory=dict)
    expires_at: float = 0.0


class ZaloPASessionStore(ABC):
    """QR-login sessions with a TTL (no DB row until the channel is created)."""

    @abstractmethod
    async def count(self) -> int:
        """Number of live sessions — enforces ``zalo_pa_max_sessions``."""

    @abstractmethod
    async def save(self, session_id: str, state: dict, ttl_secs: int) -> None: ...

    @abstractmethod
    async def load(self, session_id: str) -> dict | None: ...

    @abstractmethod
    async def delete(self, session_id: str) -> None: ...

    async def touch(self, session_id: str, state: dict, ttl_secs: int) -> None:
        """Re-save, restoring a full ``ttl_secs`` of life.

        Each QR step calls this, so a user working through the flow keeps their
        session alive; one who walks away loses it on schedule.
        """
        await self.save(session_id, state, ttl_secs)


class InProcessZaloPASessionStore(ZaloPASessionStore):
    """Sessions in a process-local dict. Correct only at ``--workers 1``."""

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}

    def _purge(self) -> None:
        now = time.monotonic()
        expired = [sid for sid, s in self._sessions.items() if s.expires_at <= now]
        for sid in expired:
            self._sessions.pop(sid, None)

    async def count(self) -> int:
        self._purge()
        return len(self._sessions)

    async def save(self, session_id: str, state: dict, ttl_secs: int) -> None:
        self._sessions[session_id] = _Session(
            state=state, expires_at=time.monotonic() + ttl_secs
        )

    async def load(self, session_id: str) -> dict | None:
        self._purge()
        sess = self._sessions.get(session_id)
        return sess.state if sess else None

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class RedisZaloPASessionStore(ZaloPASessionStore):
    """Sessions in Redis, so any worker can serve any step of the QR flow.

    The payload is **Fernet-encrypted before it is written**. A half-finished
    login already carries the Zalo cookies, ``zpw_sek`` and ``zpsid`` — the same
    material that lands in the ``EncryptedJSON`` channel config once the channel
    exists. It would be inconsistent to protect it at rest in Postgres and then
    leave it in the clear in Redis, which is typically unauthenticated on the
    internal network and dumpable with a single ``KEYS`` + ``GET``.

    Redis' own key TTL does the expiry; there is no purge sweep to run.
    """

    def __init__(self) -> None:
        self._crypto: CryptoService | None = None

    def _cipher(self) -> CryptoService:
        if self._crypto is None:
            if not settings.encryption_key:
                raise ConfigurationError(
                    "coordination_backend='redis' needs encryption_key set — "
                    "Zalo QR sessions carry credentials and are encrypted at rest."
                )
            self._crypto = CryptoService(settings.encryption_key)
        return self._crypto

    @staticmethod
    def _key(session_id: str) -> str:
        return namespaced("zalo_pa", "session", session_id)

    async def count(self) -> int:
        redis = get_redis()
        total = 0
        async for _ in redis.scan_iter(match=namespaced("zalo_pa", "session", "*")):
            total += 1
        return total

    async def save(self, session_id: str, state: dict, ttl_secs: int) -> None:
        blob = self._cipher().encrypt(orjson.dumps(state).decode())
        await get_redis().set(self._key(session_id), blob, ex=ttl_secs)

    async def load(self, session_id: str) -> dict | None:
        raw = await get_redis().get(self._key(session_id))
        if raw is None:
            return None
        try:
            return orjson.loads(self._cipher().decrypt(raw.decode()))
        except (InvalidToken, orjson.JSONDecodeError) as exc:
            # Rotated key or a corrupt write: treat as "no session" so the user
            # is sent back to step 1 rather than seeing a 500 mid-login.
            logger.warning(f"[zalo_pa] Unreadable session {session_id}: {exc}")
            await self.delete(session_id)
            return None

    async def delete(self, session_id: str) -> None:
        await get_redis().delete(self._key(session_id))


# Module-level singleton, resolved on first use from settings.
_session_store: ZaloPASessionStore | None = None


def get_session_store() -> ZaloPASessionStore:
    """Return the process-wide store, per ``settings.coordination_backend``."""
    global _session_store
    if _session_store is None:
        backend = getattr(settings, "coordination_backend", "memory")
        _session_store = (
            RedisZaloPASessionStore()
            if backend == "redis"
            else InProcessZaloPASessionStore()
        )
        logger.info(f"[zalo_pa] session store backend: {backend}")
    return _session_store


def reset_session_store() -> None:
    """Drop the cached store (tests, and lifespan shutdown)."""
    global _session_store
    _session_store = None
