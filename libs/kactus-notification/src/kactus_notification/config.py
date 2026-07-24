"""
kactus-notification settings.

Unlike kactus-data, this package does **not** extend ``CommonSettings`` — the
settings chain is linear (``CommonSettings → DataSettings → fin Settings``) and a
second library cannot insert itself into a line.  ``NotificationSettings`` is a
sibling branch off the same root instead, so an entry-point package merges it in
by multiple inheritance::

    class Settings(DataSettings, NotificationSettings): ...

MRO: ``Settings → DataSettings → CommonSettings → NotificationSettings →
BaseKactusSettings``.  Both branches descend from ``BaseKactusSettings``, so the
fields collect cleanly and the entry-point's ``model_config`` (env prefix, .env
file) still governs the whole set.

A package that never sends notifications — kactus-fin-gateway — simply does not
mix this in, and none of these variables exist in its settings.
"""

from kactus_common.config import BaseKactusSettings


class NotificationSettings(BaseKactusSettings):
    """Settings owned by kactus-notification.

    Not an entry point: no ``model_config`` / ``.env`` of its own.  Values come
    from whichever entry-point package inherits this alongside its own chain.
    """

    # Synchronous bounded retry on transport errors (all channels)
    notification_max_send_attempts: int = 3  # total tries per send (1 = no retry)
    notification_retry_base_delay: float = 1.0  # exp backoff: 1s, 2s, 4s, …

    # Redis Streams delivery queue (kactus_notification.queue).
    # Requires coordination_backend=redis; on `memory` the API sends inline and
    # none of this applies — see `_queue_enabled()` in kactus_fin/notification/api.py.
    notification_queue_enabled: bool = True
    notification_queue_maxlen: int = 10_000  # buffer cap; the audit is in Postgres
    notification_queue_batch: int = 10  # entries per XREADGROUP
    notification_queue_block_ms: int = 5_000  # how long one read waits for work
    # An entry idle this long is assumed abandoned by its consumer and reclaimed.
    # Must comfortably exceed the worst-case send: max_send_attempts with
    # exponential backoff, or a live send gets picked up by a second worker too.
    notification_queue_claim_idle_ms: int = 60_000
    notification_queue_max_deliveries: int = 5  # then drop, or it loops forever

    # Zalo PA (unofficial personal-account channel via zlapi + curl_cffi QR login)
    # Residential proxy is required in non-dev — datacenter IP/TLS is blocked by
    # Zalo's anti-fraud. Left empty ⇒ QR login only works from a dev/residential IP.
    zalo_pa_proxy_url: str = ""  # e.g. http://user:pass@host:port (BrightData)
    zalo_pa_session_ttl_secs: int = 300  # QR-login session lifetime in the store
    zalo_pa_max_sessions: int = 50  # cap on concurrent in-flight QR logins
