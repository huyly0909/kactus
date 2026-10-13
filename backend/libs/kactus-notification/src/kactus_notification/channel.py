"""Channel strategy base — one subclass per channel type under ``channels/``.

A channel knows how to (a) open/close its transport ("connection"), (b) send a
:class:`RenderedMessage`, and (c) test its credentials. Methods are
**synchronous/blocking** (``requests``), mirroring ``AssetProvider``; the async
:class:`~kactus_notification.dispatcher.Notifier` wraps a send in
``asyncio.to_thread`` so any async caller (kactus-data, kactus-fin) can deliver
without blocking the event loop.

The ``config`` is a validated Pydantic schema from the channel's own
``channels/<type>/schema.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

import requests

from .const import NotificationChannelType
from .schema import BaseChannelConfig, Recipient


@dataclass
class RenderedMessage:
    """A channel-ready payload produced by a template.

    ``text`` is the plain/markup body (Telegram). ``payload`` is an optional
    channel-native JSON body (e.g. Slack Block Kit); when set it takes priority.
    """

    text: str
    payload: dict | None = None


@dataclass
class DeliveryTarget:
    """Outcome of delivering one message to **one** conversation.

    Only fan-out channels (Zalo PA, which sends to every saved conversation)
    produce these; Telegram/Slack have a single implicit target and leave
    ``last_targets`` empty. Persisted verbatim onto ``NotificationLog.targets``,
    so a log row answers *which* conversations got the message — the fan-out
    used to be invisible above ``send()``.
    """

    thread_id: str
    thread_type: int
    name: str | None
    ok: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "thread_id": self.thread_id,
            "thread_type": self.thread_type,
            "name": self.name,
            "ok": self.ok,
            "error": self.error,
        }


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
        # Per-conversation outcome of the most recent send(). An attribute rather
        # than a return value because a send that delivers to nobody *raises* —
        # and that is exactly the case whose per-target errors we must log.
        self.last_targets: list[DeliveryTarget] = []

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
        """Deliver ``message`` (blocking). Raises on transport/HTTP error.

        Fan-out channels record one :class:`DeliveryTarget` per conversation in
        ``self.last_targets`` — including on the raising path.
        """

    @abstractmethod
    def test_connection(self) -> bool:
        """Validate credentials/config (blocking)."""

    # ---- optional: recipient discovery (Zalo picker; HTTP channels skip) --- #
    def list_recipients(self, query: str = "") -> list[Recipient]:
        """Return pickable send targets. Only channels with a directory (Zalo)."""
        raise NotImplementedError(
            f"{self.channel_type} channels have no recipient directory"
        )
