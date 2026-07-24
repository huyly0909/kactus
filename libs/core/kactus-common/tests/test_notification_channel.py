"""Tests for kactus-common notification channels, templates, and the registry.

No DB / no network: a ``FakeSession`` is injected so ``send`` / ``test_connection``
build the right request without hitting Telegram/Slack. (Real delivery is covered
by the live smoke test — mocked HTTP can hide real API quirks.)
"""

from __future__ import annotations

import pytest
import requests
from kactus_common.notification.channel import (
    RenderedMessage,
    SlackChannel,
    TelegramChannel,
)
from kactus_common.notification.const import NotificationChannelType, NotificationLevel
from kactus_common.notification.registry import build_channel, get_template
from kactus_common.notification.schema import (
    NotificationEvent,
    SlackChannelConfig,
    TelegramChannelConfig,
)
from pydantic import ValidationError


class FakeResponse:
    def __init__(self, status_code: int = 200, json_data: dict | None = None) -> None:
        self.status_code = status_code
        self._json = json_data or {}

    def json(self) -> dict:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class FakeSession:
    def __init__(self, response: FakeResponse | None = None) -> None:
        self.response = response or FakeResponse()
        self.posts: list[dict] = []
        self.gets: list[dict] = []
        self.closed = False

    def post(self, url, json=None, timeout=None):
        self.posts.append({"url": url, "json": json, "timeout": timeout})
        return self.response

    def get(self, url, timeout=None):
        self.gets.append({"url": url, "timeout": timeout})
        return self.response

    def close(self):
        self.closed = True


# --------------------------------------------------------------------------- #
# Registry / factory
# --------------------------------------------------------------------------- #
def test_build_channel_parses_config_by_type():
    ch = build_channel(
        NotificationChannelType.TELEGRAM,
        {"bot_token": "t", "chat_id": "1"},
    )
    assert isinstance(ch, TelegramChannel)
    assert isinstance(ch.config, TelegramChannelConfig)
    assert ch.config.parse_mode == "HTML"  # default applied


def test_build_channel_invalid_config_raises():
    with pytest.raises(ValidationError):
        build_channel(NotificationChannelType.TELEGRAM, {})  # missing required fields


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #
def test_telegram_template_renders_html():
    event = NotificationEvent(
        title="Giá vàng",
        body="SJC tăng",
        level=NotificationLevel.WARNING,
        fields=[("Mua", "75.0"), ("Bán", "77.0")],
        url="https://example.com",
    )
    msg = get_template(NotificationChannelType.TELEGRAM).render(event)
    assert "<b>Giá vàng</b>" in msg.text
    assert "⚠️" in msg.text
    assert "<b>Mua:</b> 75.0" in msg.text
    assert 'href="https://example.com"' in msg.text
    assert msg.payload is None


def test_telegram_template_escapes_html():
    msg = get_template(NotificationChannelType.TELEGRAM).render(
        NotificationEvent(title="<script>", body="a & b")
    )
    assert "<script>" not in msg.text  # escaped
    assert "&lt;script&gt;" in msg.text
    assert "a &amp; b" in msg.text


def test_slack_template_renders_blocks():
    event = NotificationEvent(title="Alert", body="body", fields=[("k", "v")])
    msg = get_template(NotificationChannelType.SLACK).render(event)
    assert msg.payload is not None
    assert msg.payload["blocks"][0]["type"] == "header"
    assert msg.payload["text"] == "Alert"  # push-notification fallback


# --------------------------------------------------------------------------- #
# Channel send / test_connection (FakeSession injected)
# --------------------------------------------------------------------------- #
def test_telegram_send_builds_request():
    ch = TelegramChannel(TelegramChannelConfig(bot_token="TOK", chat_id="42"))
    ch._session = FakeSession()
    ch.send(RenderedMessage(text="hello"))
    sent = ch._session.posts[0]
    assert sent["url"].endswith("/botTOK/sendMessage")
    assert sent["json"] == {"chat_id": "42", "text": "hello", "parse_mode": "HTML"}


def test_telegram_send_raises_on_http_error():
    ch = TelegramChannel(TelegramChannelConfig(bot_token="TOK", chat_id="42"))
    ch._session = FakeSession(FakeResponse(status_code=400))
    with pytest.raises(requests.HTTPError):
        ch.send(RenderedMessage(text="x"))


def test_telegram_test_connection():
    ok = TelegramChannel(TelegramChannelConfig(bot_token="T", chat_id="1"))
    ok._session = FakeSession(FakeResponse(200, {"ok": True}))
    assert ok.test_connection() is True

    bad = TelegramChannel(TelegramChannelConfig(bot_token="T", chat_id="1"))
    bad._session = FakeSession(FakeResponse(401, {"ok": False}))
    assert bad.test_connection() is False


def test_slack_send_posts_payload():
    ch = SlackChannel(
        SlackChannelConfig(webhook_url="https://hooks.slack.com/services/a/b/c")
    )
    ch._session = FakeSession()
    ch.send(RenderedMessage(text="t", payload={"blocks": [{"type": "divider"}]}))
    assert ch._session.posts[0]["url"] == "https://hooks.slack.com/services/a/b/c"
    assert ch._session.posts[0]["json"] == {"blocks": [{"type": "divider"}]}


def test_slack_test_connection_validates_url_shape():
    good = SlackChannel(
        SlackChannelConfig(webhook_url="https://hooks.slack.com/services/a")
    )
    assert good.test_connection() is True
    bad = SlackChannel(SlackChannelConfig(webhook_url="https://evil.example/x"))
    assert bad.test_connection() is False


# --------------------------------------------------------------------------- #
# Connection lifecycle
# --------------------------------------------------------------------------- #
def test_connection_lifecycle():
    ch = TelegramChannel(TelegramChannelConfig(bot_token="T", chat_id="1"))
    assert ch._session is None
    ch.create_connection()
    assert ch._session is not None
    ch.create_connection()  # idempotent — no new session
    first = ch._session
    assert ch._session is first
    ch.close_connection()
    assert ch._session is None
    ch.close_connection()  # idempotent

    # update_connection swaps config and reconnects
    ch.update_connection(TelegramChannelConfig(bot_token="T2", chat_id="2"))
    assert ch.config.bot_token == "T2"
    assert ch._session is not None
    ch.delete_connection()
    assert ch._session is None


def test_context_manager_opens_and_closes():
    ch = TelegramChannel(TelegramChannelConfig(bot_token="T", chat_id="1"))
    with ch as opened:
        assert opened._session is not None
    assert ch._session is None


def test_send_without_connection_raises():
    ch = TelegramChannel(TelegramChannelConfig(bot_token="T", chat_id="1"))
    with pytest.raises(RuntimeError):
        ch.send(RenderedMessage(text="x"))
