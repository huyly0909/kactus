"""Channel strategies — one :class:`BaseNotificationChannel` per channel type.

A channel knows how to (a) open/close its transport ("connection"), (b) send a
:class:`RenderedMessage`, and (c) test its credentials. Methods are
**synchronous/blocking** (``requests``), mirroring ``AssetProvider``; the async
:class:`~kactus_common.notification.dispatcher.Notifier` wraps a send in
``asyncio.to_thread`` so any async caller (kactus-data, kactus-fin) can deliver
without blocking the event loop.

The ``config`` is a validated Pydantic schema from this package's ``schema``
module.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

import requests
from kactus_common.exceptions import ExternalServiceError
from zlapi.models import ZaloAPIException

from .const import NotificationChannelType
from .schema import (
    BaseChannelConfig,
    Recipient,
    SlackChannelConfig,
    TelegramChannelConfig,
    ZaloPAChannelConfig,
)


@dataclass
class RenderedMessage:
    """A channel-ready payload produced by a template.

    ``text`` is the plain/markup body (Telegram). ``payload`` is an optional
    channel-native JSON body (e.g. Slack Block Kit); when set it takes priority.
    """

    text: str
    payload: dict | None = None


class BaseNotificationChannel(ABC):
    """Connection lifecycle + send for one channel type.

    The "connection" is a pooled :class:`requests.Session`; ``create_connection``
    opens it and ``close_connection`` releases it, so repeated sends reuse the
    same transport.
    """

    channel_type: ClassVar[NotificationChannelType]
    config_schema: ClassVar[type[BaseChannelConfig]]

    # Transient transport errors the dispatcher may retry (per-channel). Default
    # covers the HTTP channels (Telegram/Slack via ``requests``); Zalo PA extends
    # it with its zlapi/websocket errors. Deterministic failures (expired session,
    # validation) must raise ``ExternalServiceError`` instead → never retried.
    retryable_exceptions: ClassVar[tuple[type[BaseException], ...]] = (
        requests.RequestException,
    )

    def __init__(self, config: BaseChannelConfig) -> None:
        self.config = config
        self._session: requests.Session | None = None

    # ---- connection lifecycle (sync, cheap) -------------------------------- #
    def create_connection(self) -> None:
        """Open the transport (idempotent)."""
        if self._session is None:
            self._session = requests.Session()

    def close_connection(self) -> None:
        """Release the transport (idempotent)."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def update_connection(self, config: BaseChannelConfig) -> None:
        """Swap config and reconnect."""
        self.close_connection()
        self.config = config
        self.create_connection()

    def delete_connection(self) -> None:
        """Tear down the channel (release the transport)."""
        self.close_connection()

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            raise RuntimeError("connection not open — call create_connection() first")
        return self._session

    def __enter__(self) -> "BaseNotificationChannel":
        self.create_connection()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close_connection()

    # ---- behaviour (blocking; wrapped in to_thread by the async caller) ---- #
    @abstractmethod
    def send(self, message: RenderedMessage) -> None:
        """Deliver ``message`` (blocking). Raises on transport/HTTP error."""

    @abstractmethod
    def test_connection(self) -> bool:
        """Validate credentials/config (blocking)."""

    # ---- optional: recipient discovery (Zalo picker; HTTP channels skip) --- #
    def list_recipients(self, query: str = "") -> list[Recipient]:
        """Return pickable send targets. Only channels with a directory (Zalo)."""
        raise NotImplementedError(
            f"{self.channel_type} channels have no recipient directory"
        )


class TelegramChannel(BaseNotificationChannel):
    """Telegram Bot API — ``sendMessage`` to a chat; ``getMe`` to validate."""

    channel_type = NotificationChannelType.TELEGRAM
    config_schema = TelegramChannelConfig
    _API = "https://api.telegram.org"

    def send(self, message: RenderedMessage) -> None:
        cfg: TelegramChannelConfig = self.config  # type: ignore[assignment]
        resp = self.session.post(
            f"{self._API}/bot{cfg.bot_token}/sendMessage",
            json={
                "chat_id": cfg.chat_id,
                "text": message.text,
                "parse_mode": cfg.parse_mode,
            },
            timeout=cfg.timeout,
        )
        resp.raise_for_status()

    def test_connection(self) -> bool:
        cfg: TelegramChannelConfig = self.config  # type: ignore[assignment]
        resp = self.session.get(
            f"{self._API}/bot{cfg.bot_token}/getMe", timeout=cfg.timeout
        )
        return resp.status_code == 200 and bool(resp.json().get("ok"))


class SlackChannel(BaseNotificationChannel):
    """Slack Incoming Webhook — POST the message body to the webhook URL."""

    channel_type = NotificationChannelType.SLACK
    config_schema = SlackChannelConfig
    _WEBHOOK_PREFIX = "https://hooks.slack.com/"

    def send(self, message: RenderedMessage) -> None:
        cfg: SlackChannelConfig = self.config  # type: ignore[assignment]
        body = (
            message.payload if message.payload is not None else {"text": message.text}
        )
        resp = self.session.post(cfg.webhook_url, json=body, timeout=cfg.timeout)
        resp.raise_for_status()

    def test_connection(self) -> bool:
        # Incoming webhooks have no introspection endpoint — validate URL shape so
        # a "test" doesn't post a stray message to the channel.
        return self.config.webhook_url.startswith(self._WEBHOOK_PREFIX)  # type: ignore[attr-defined]


class ZaloPAChannel(BaseNotificationChannel):
    """Zalo Personal Account — push a text report to a chosen friend/group.

    Unlike the HTTP channels the "connection" is a blocking ``zlapi.ZaloAPI``
    built from the login session in ``config`` (no ``requests.Session``). The
    build + send run inside the dispatcher's ``asyncio.to_thread``, so this stays
    synchronous like the others. An expired/invalid session surfaces as a
    ``ZaloAPIException`` → re-raised as a **non-retryable** ``ExternalServiceError``
    (re-scan the QR); genuine transport hiccups stay retryable.
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
        # Import here so the module's os.kill guard is applied and to avoid a
        # circular import (zalo_pa imports schema, channel imports zalo_pa).
        from .zalo_pa import build_sync_bot

        if self._bot is None:
            self._bot = build_sync_bot(self.config)  # type: ignore[arg-type]

    def close_connection(self) -> None:
        self._bot = None

    def send(self, message: RenderedMessage) -> None:
        from .zalo_pa import send_text_sync

        cfg: ZaloPAChannelConfig = self.config  # type: ignore[assignment]
        try:
            send_text_sync(self._bot, message.text, cfg.thread_id, cfg.thread_type)
        except ZaloAPIException as exc:  # expired session / API refusal → no retry
            raise ExternalServiceError(
                f"Zalo PA send failed (session may be expired — re-scan QR): {exc}"
            ) from exc

    def test_connection(self) -> bool:
        try:
            return bool(self._bot.fetchAccountInfo())
        except ZaloAPIException:
            return False

    def list_recipients(self, query: str = "") -> list[Recipient]:
        import asyncio

        from .zalo_pa import ZlapiAsync

        cfg: ZaloPAChannelConfig = self.config  # type: ignore[assignment]
        creds = {
            "cookies": cfg.cookies,
            "imei": cfg.imei,
            "user_agent": cfg.user_agent,
        }

        async def _run() -> list[Recipient]:
            client = await ZlapiAsync.create(creds)
            return await client.list_recipients(query)

        return asyncio.run(_run())
