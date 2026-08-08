"""Telegram Bot API setup helpers — verify a token, find the chat id.

Telegram never shows a channel's numeric id in its UI, and ``-100…`` ids are not
guessable, so a user who has a bot and a channel still cannot configure a
channel without this. ``getUpdates`` is the only way to learn the id: the bot
sees a chat once it is an administrator there **and** something has been posted
since.

These are module-level functions rather than methods on
:class:`TelegramChannel` because discovery runs *before* a config exists —
``TelegramChannelConfig.chat_id`` is required, so building a channel just to
call ``getUpdates`` would need a placeholder chat id.

Blocking ``requests`` calls wrapped in ``asyncio.to_thread``, matching how
:class:`~kactus_notification.dispatcher.Notifier` drives ``send``/
``test_connection``.
"""

from __future__ import annotations

import asyncio

import requests
from kactus_common.exceptions import ExternalServiceError

from .schema import TelegramBotInfo, TelegramChat

API = "https://api.telegram.org"

#: The ⚡ probe — a real message, so it proves what ``getMe`` cannot: that the
#: bot may actually post to *this* chat (admin + "Post messages").
TEST_MESSAGE_TITLE = "Test message"
TEST_GREETING = "Hello, nice to meet you"

# Update kinds that carry a chat. Passed as ``allowed_updates`` so a previously
# restricted getUpdates call (Telegram remembers the last value) cannot hide
# channel posts from us.
CHAT_UPDATE_KINDS = (
    "message",
    "edited_message",
    "channel_post",
    "edited_channel_post",
    "my_chat_member",
    "chat_member",
)
# ``chat_member`` is NOT in Telegram's default allowed_updates — it only arrives
# when asked for by name, and it names a chat, so discovery must request it.
_ALLOWED_UPDATES = [*CHAT_UPDATE_KINDS, "callback_query"]

# Read the tail of the update queue. A **negative** offset returns the last N
# updates *without confirming them*; any non-negative offset advances Telegram's
# cursor and would consume updates belonging to a real consumer (a bot that also
# runs a poller elsewhere). Discovery must stay side-effect free.
DISCOVER_OFFSET = -100


def _call(bot_token: str, method: str, timeout: float, payload: dict | None = None):
    """One Bot API call. Returns ``result``; raises ``ExternalServiceError``."""
    try:
        resp = requests.post(
            f"{API}/bot{bot_token}/{method}", json=payload or {}, timeout=timeout
        )
    except requests.RequestException as exc:
        raise ExternalServiceError(f"Telegram {method} failed: {exc}") from exc
    try:
        data = resp.json()
    except ValueError as exc:
        raise ExternalServiceError(
            f"Telegram {method} returned a non-JSON response (HTTP {resp.status_code})"
        ) from exc
    if not data.get("ok"):
        detail = data.get("description") or f"HTTP {resp.status_code}"
        raise ExternalServiceError(f"Telegram {method} failed: {detail}")
    return data.get("result")


def _to_chat(chat: dict) -> TelegramChat:
    """Map a Bot API ``Chat`` to the pickable shape the UI renders."""
    chat_id = str(chat.get("id", ""))
    name = (
        chat.get("title")
        or chat.get("username")
        or " ".join(filter(None, (chat.get("first_name"), chat.get("last_name"))))
        or chat_id
    )
    return TelegramChat(
        id=chat_id,
        title=str(name),
        type=str(chat.get("type", "")),
        username=chat.get("username"),
    )


def _chats_in(update: dict):
    """Every chat referenced by one update, whatever kind it is."""
    for kind in CHAT_UPDATE_KINDS:
        payload = update.get(kind)
        if isinstance(payload, dict) and isinstance(payload.get("chat"), dict):
            yield payload["chat"]
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        message = callback.get("message")
        if isinstance(message, dict) and isinstance(message.get("chat"), dict):
            yield message["chat"]


def _verify_blocking(bot_token: str, timeout: float) -> TelegramBotInfo:
    result = _call(bot_token, "getMe", timeout) or {}
    return TelegramBotInfo(
        id=str(result.get("id", "")),
        username=str(result.get("username") or ""),
        first_name=str(result.get("first_name") or ""),
    )


def _discover_blocking(bot_token: str, timeout: float) -> list[TelegramChat]:
    webhook = _call(bot_token, "getWebhookInfo", timeout) or {}
    if webhook.get("url"):
        # Telegram answers getUpdates with a 409 while a webhook is registered;
        # say what is actually wrong instead of surfacing that bare conflict.
        raise ExternalServiceError(
            f"A webhook is registered for this bot ({webhook['url']}), so Telegram "
            "disables getUpdates. Remove it with deleteWebhook, or read the chat id "
            "from the webhook payload."
        )
    updates = (
        _call(
            bot_token,
            "getUpdates",
            timeout,
            {
                "offset": DISCOVER_OFFSET,
                "timeout": 0,
                "allowed_updates": _ALLOWED_UPDATES,
            },
        )
        or []
    )
    # An empty list is the normal first-run state (nothing posted since the bot
    # became admin, or Telegram dropped updates older than 24h) — not an error.
    # The caller shows the "add the bot as admin, then post" guide.
    seen: dict[str, TelegramChat] = {}
    for update in updates:
        if not isinstance(update, dict):
            continue
        for chat in _chats_in(update):
            mapped = _to_chat(chat)
            if mapped.id and mapped.id not in seen:
                seen[mapped.id] = mapped
    return list(seen.values())


def _resolve_blocking(bot_token: str, chat_id: str, timeout: float) -> TelegramChat:
    result = _call(bot_token, "getChat", timeout, {"chat_id": chat_id}) or {}
    return _to_chat(result)


async def verify_bot(bot_token: str, timeout: float = 10.0) -> TelegramBotInfo:
    """``getMe`` — confirm the token is live and name the bot."""
    return await asyncio.to_thread(_verify_blocking, bot_token, timeout)


async def discover_chats(bot_token: str, timeout: float = 10.0) -> list[TelegramChat]:
    """Every chat the bot can currently see, deduped. May legitimately be empty."""
    return await asyncio.to_thread(_discover_blocking, bot_token, timeout)


async def resolve_chat(
    bot_token: str, chat_id: str, timeout: float = 10.0
) -> TelegramChat:
    """``getChat`` — resolve a typed id or ``@public_name`` to a full chat."""
    return await asyncio.to_thread(_resolve_blocking, bot_token, chat_id, timeout)
