"""Tests for the Notifier orchestrator (kactus-common).

Exercises the real send/test path — build_channel + template render + the
``asyncio.to_thread`` blocking helpers + connection lifecycle — with a fake
``requests`` session injected (no network). Transport errors → ``ExternalServiceError``.
"""

from __future__ import annotations

import types

import pytest
import requests
from kactus_common.exceptions import ExternalServiceError
from kactus_common.notification import dispatcher
from kactus_common.notification.channel import TelegramChannel
from kactus_common.notification.schema import NotificationEvent, TelegramChannelConfig


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
    def __init__(
        self, response: FakeResponse | None = None, *, boom: bool = False
    ) -> None:
        self.response = response or FakeResponse()
        self.boom = boom
        self.posts: list[dict] = []
        self.closed = False

    def post(self, url, json=None, timeout=None):
        if self.boom:
            raise requests.ConnectionError("boom")
        self.posts.append({"url": url, "json": json})
        return self.response

    def get(self, url, timeout=None):
        if self.boom:
            raise requests.ConnectionError("boom")
        return self.response

    def close(self):
        self.closed = True


def _model():
    """Minimal stand-in for the ORM channel — Notifier reads only these attrs."""
    return types.SimpleNamespace(
        id=1, channel_type="telegram", config={"bot_token": "T", "chat_id": "1"}
    )


def _patch_channel(monkeypatch, fake: FakeSession) -> TelegramChannel:
    ch = TelegramChannel(TelegramChannelConfig(bot_token="T", chat_id="1"))
    # create_connection installs our fake instead of opening a real Session.
    monkeypatch.setattr(ch, "create_connection", lambda: setattr(ch, "_session", fake))
    monkeypatch.setattr(dispatcher, "build_channel", lambda t, c: ch)
    return ch


@pytest.mark.asyncio
async def test_send_event_renders_and_delivers(monkeypatch):
    fake = FakeSession()
    _patch_channel(monkeypatch, fake)
    await dispatcher.Notifier.send_event(
        _model(), NotificationEvent(title="Giá vàng", body="SJC tăng")
    )
    assert fake.posts and fake.posts[0]["url"].endswith("/botT/sendMessage")
    assert "Giá vàng" in fake.posts[0]["json"]["text"]
    assert fake.closed is True  # connection closed after send


@pytest.mark.asyncio
async def test_send_event_wraps_transport_error(monkeypatch):
    _patch_channel(monkeypatch, FakeSession(FakeResponse(status_code=500)))
    with pytest.raises(ExternalServiceError):
        await dispatcher.Notifier.send_event(_model(), NotificationEvent(title="x"))


@pytest.mark.asyncio
async def test_test_success(monkeypatch):
    _patch_channel(monkeypatch, FakeSession(FakeResponse(200, {"ok": True})))
    assert await dispatcher.Notifier.test(_model()) is True


@pytest.mark.asyncio
async def test_test_returns_false_on_transport_error(monkeypatch):
    _patch_channel(monkeypatch, FakeSession(boom=True))
    assert await dispatcher.Notifier.test(_model()) is False
