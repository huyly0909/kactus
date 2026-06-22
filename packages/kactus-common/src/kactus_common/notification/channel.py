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

from .const import NotificationChannelType
from .schema import BaseChannelConfig, SlackChannelConfig, TelegramChannelConfig


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
