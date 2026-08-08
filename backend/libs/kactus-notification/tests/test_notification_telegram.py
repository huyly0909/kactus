"""Tests for the Telegram setup helpers (verify / discover / resolve).

No network: ``requests.post`` is faked. The behaviours worth pinning are the
ones that make chat-id discovery usable and safe — the webhook conflict, the
non-consuming offset, dedup across update kinds, and "empty is not an error".
"""

from __future__ import annotations

import pytest
import requests
from kactus_common.exceptions import ExternalServiceError
from kactus_notification.channels.telegram import client as tg


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def fake_api(monkeypatch, responses: dict, calls: list | None = None):
    """Route ``bot<token>/<method>`` to a canned payload, recording the bodies."""

    def _post(url, json=None, timeout=None):  # noqa: A002 — mirrors requests' kwarg
        method = url.rsplit("/", 1)[-1]
        if calls is not None:
            calls.append((method, json))
        if method not in responses:
            raise AssertionError(f"unexpected Telegram call: {method}")
        payload = responses[method]
        if isinstance(payload, Exception):
            raise payload
        return FakeResponse(payload)

    monkeypatch.setattr(tg.requests, "post", _post)


def ok(result):
    return {"ok": True, "result": result}


NO_WEBHOOK = ok({"url": ""})


# --------------------------------------------------------------------------- #
# verify_bot
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_verify_bot_returns_identity(monkeypatch):
    fake_api(
        monkeypatch,
        {"getMe": ok({"id": 123, "username": "gold_bot", "first_name": "Gold"})},
    )
    info = await tg.verify_bot("TOKEN")
    assert (info.id, info.username, info.first_name) == ("123", "gold_bot", "Gold")


@pytest.mark.asyncio
async def test_bad_token_surfaces_telegram_description(monkeypatch):
    fake_api(
        monkeypatch,
        {"getMe": {"ok": False, "description": "Unauthorized"}},
    )
    with pytest.raises(ExternalServiceError, match="Unauthorized"):
        await tg.verify_bot("BAD")


@pytest.mark.asyncio
async def test_transport_error_is_wrapped(monkeypatch):
    fake_api(monkeypatch, {"getMe": requests.ConnectionError("no route")})
    with pytest.raises(ExternalServiceError, match="no route"):
        await tg.verify_bot("TOKEN")


# --------------------------------------------------------------------------- #
# discover_chats
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_discover_refuses_while_a_webhook_is_set(monkeypatch):
    """Telegram 409s getUpdates behind a webhook — say so, and how to fix it."""
    calls: list = []
    fake_api(
        monkeypatch,
        {"getWebhookInfo": ok({"url": "https://hooks.example/tg"})},
        calls,
    )
    with pytest.raises(ExternalServiceError, match="deleteWebhook"):
        await tg.discover_chats("TOKEN")
    # …and it never even attempted the doomed call.
    assert [m for m, _ in calls] == ["getWebhookInfo"]


@pytest.mark.asyncio
async def test_discover_uses_a_non_consuming_offset(monkeypatch):
    """A non-negative offset would confirm updates and rob a real poller."""
    calls: list = []
    fake_api(
        monkeypatch,
        {"getWebhookInfo": NO_WEBHOOK, "getUpdates": ok([])},
        calls,
    )
    await tg.discover_chats("TOKEN")

    body = dict(calls[-1][1])
    assert body["offset"] < 0
    assert body["timeout"] == 0
    # channel_post must be requested explicitly: Telegram remembers the last
    # allowed_updates, so a previously restricted bot would hide channels.
    assert "channel_post" in body["allowed_updates"]


@pytest.mark.asyncio
async def test_discover_dedupes_across_update_kinds(monkeypatch):
    """One chat seen via several update kinds is still one row."""
    channel = {"id": -1001234567890, "title": "Gold Alerts", "type": "channel"}
    group = {"id": -42, "title": "Trading Desk", "type": "group"}
    private = {"id": 7, "first_name": "Ana", "last_name": "Vu", "type": "private"}
    fake_api(
        monkeypatch,
        {
            "getWebhookInfo": NO_WEBHOOK,
            "getUpdates": ok(
                [
                    {"channel_post": {"chat": channel}},
                    {"edited_channel_post": {"chat": channel}},
                    {"my_chat_member": {"chat": channel}},
                    {"message": {"chat": group}},
                    {"callback_query": {"message": {"chat": private}}},
                ]
            ),
        },
    )
    chats = await tg.discover_chats("TOKEN")

    assert [c.id for c in chats] == ["-1001234567890", "-42", "7"]
    assert [c.type for c in chats] == ["channel", "group", "private"]
    # Display name falls back through title → username → first+last name.
    assert [c.title for c in chats] == ["Gold Alerts", "Trading Desk", "Ana Vu"]


@pytest.mark.asyncio
async def test_discover_empty_is_not_an_error(monkeypatch):
    """The normal first run: bot is admin but nobody has posted yet."""
    fake_api(
        monkeypatch,
        {"getWebhookInfo": NO_WEBHOOK, "getUpdates": ok([])},
    )
    assert await tg.discover_chats("TOKEN") == []


@pytest.mark.asyncio
async def test_discover_ignores_updates_without_a_chat(monkeypatch):
    fake_api(
        monkeypatch,
        {
            "getWebhookInfo": NO_WEBHOOK,
            "getUpdates": ok([{"poll": {"id": "p1"}}, {"update_id": 1}]),
        },
    )
    assert await tg.discover_chats("TOKEN") == []


# --------------------------------------------------------------------------- #
# resolve_chat
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_resolve_chat_maps_a_public_username(monkeypatch):
    calls: list = []
    fake_api(
        monkeypatch,
        {
            "getChat": ok(
                {
                    "id": -1009876543210,
                    "title": "Public News",
                    "type": "channel",
                    "username": "public_news",
                }
            )
        },
        calls,
    )
    chat = await tg.resolve_chat("TOKEN", "@public_news")

    assert calls[-1][1]["chat_id"] == "@public_news"
    assert chat.id == "-1009876543210"  # the numeric id worth storing
    assert chat.username == "public_news"
