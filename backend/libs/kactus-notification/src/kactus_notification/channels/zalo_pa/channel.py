"""Zalo Personal Account transport (fan-out to every saved conversation)."""

from __future__ import annotations

import time
from typing import ClassVar

import requests
from kactus_common.exceptions import ExternalServiceError
from loguru import logger
from zlapi.models import ZaloAPIException

from ...channel import BaseNotificationChannel, DeliveryTarget, RenderedMessage
from ...const import NotificationChannelType
from . import client
from .schema import ZaloPAChannelConfig


class ZaloPAChannel(BaseNotificationChannel):
    """Zalo Personal Account — push a text report to a chosen friend/group.

    Unlike the HTTP channels the "connection" is a blocking ``zlapi.ZaloAPI``
    built from the login session in ``config`` (no ``requests.Session``). The
    build + send run inside the dispatcher's ``asyncio.to_thread``, so this stays
    synchronous like the others. An expired/invalid session surfaces as a
    ``ZaloAPIException`` → re-raised as a **non-retryable** ``ExternalServiceError``
    (re-scan the QR); genuine transport hiccups stay retryable.

    Importing ``.client`` at module scope applies its ``os.kill`` guard before
    any ``zlapi`` object is constructed. It is imported as a *module* (not
    ``from .client import build_sync_bot``) so the lookups below resolve at call
    time — that keeps the transport swappable under test.
    """

    channel_type = NotificationChannelType.ZALO_PA
    config_schema = ZaloPAChannelConfig
    # Transient network errors zlapi surfaces via ``requests`` → retry.
    retryable_exceptions: ClassVar[tuple[type[BaseException], ...]] = (
        requests.RequestException,
        ConnectionError,
        TimeoutError,
    )

    def __init__(self, config: ZaloPAChannelConfig) -> None:
        super().__init__(config)
        self._bot = None

    def create_connection(self) -> None:
        if self._bot is None:
            self._bot = client.build_sync_bot(self.config)  # type: ignore[arg-type]

    def close_connection(self) -> None:
        self._bot = None

    def send(self, message: RenderedMessage) -> None:
        """Deliver to every saved conversation, sequentially with an anti-spam gap.

        Partial-failure rule: once **any** target got the message, never raise —
        the dispatcher retries the *whole* ``send()``, which would double-send to
        targets that already received it. With zero deliveries, a transient
        transport error re-raises (safe to retry the batch); otherwise the
        ``ZaloAPIException``s mean the session is dead → non-retryable.

        Every conversation's outcome lands in ``self.last_targets`` on both
        paths, so a partial send is auditable instead of a bare "success".
        """
        cfg: ZaloPAChannelConfig = self.config  # type: ignore[assignment]
        self.last_targets = []
        if not cfg.recipients:
            raise ExternalServiceError(
                "Zalo PA channel has no saved conversations — edit the channel"
            )
        delivered = 0
        transient_err: Exception | None = None
        session_err: Exception | None = None
        for index, target in enumerate(cfg.recipients):
            if index:
                time.sleep(client.SEND_DELAY_SECS)
            try:
                client.send_text_sync(
                    self._bot, message.text, target.thread_id, target.thread_type
                )
                delivered += 1
                self.last_targets.append(
                    DeliveryTarget(
                        thread_id=target.thread_id,
                        thread_type=target.thread_type,
                        name=target.name,
                        ok=True,
                    )
                )
            except ZaloAPIException as exc:  # expired session / API refusal
                session_err = exc
                self.last_targets.append(
                    DeliveryTarget(
                        thread_id=target.thread_id,
                        thread_type=target.thread_type,
                        name=target.name,
                        ok=False,
                        error=str(exc),
                    )
                )
                logger.warning(
                    "[zalo_pa] send to {tid} failed: {exc}",
                    tid=target.thread_id,
                    exc=exc,
                )
            except self.retryable_exceptions as exc:  # transient transport error
                transient_err = exc
                self.last_targets.append(
                    DeliveryTarget(
                        thread_id=target.thread_id,
                        thread_type=target.thread_type,
                        name=target.name,
                        ok=False,
                        error=str(exc),
                    )
                )
                logger.warning(
                    "[zalo_pa] send to {tid} hit transport error: {exc}",
                    tid=target.thread_id,
                    exc=exc,
                )
        if delivered:
            return  # per-target failures already logged; never retry a partial send
        if transient_err is not None and session_err is None:
            raise transient_err  # nothing delivered → batch retry is safe
        raise ExternalServiceError(
            "Zalo PA send failed for all "
            f"{len(cfg.recipients)} conversation(s) "
            f"(session may be expired — re-scan QR): {session_err or transient_err}"
        ) from (session_err or transient_err)

    def test_connection(self) -> bool:
        try:
            return bool(self._bot.fetchAccountInfo())
        except ZaloAPIException:
            return False
