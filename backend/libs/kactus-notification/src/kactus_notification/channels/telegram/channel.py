"""Telegram Bot API transport."""

from __future__ import annotations

from ...channel import BaseNotificationChannel, RenderedMessage
from ...const import NotificationChannelType
from .schema import TelegramChannelConfig

API = "https://api.telegram.org"


class TelegramChannel(BaseNotificationChannel):
    """Telegram Bot API — ``sendMessage`` to a chat; ``getMe`` to validate."""

    channel_type = NotificationChannelType.TELEGRAM
    config_schema = TelegramChannelConfig
    _API = API

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
