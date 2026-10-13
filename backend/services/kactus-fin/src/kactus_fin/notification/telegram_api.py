"""Telegram onboarding API — verify a bot token, find the chat id, repoint a channel.

Telegram gives no way to read a channel's numeric id from its own UI, so these
routes back the setup wizard: probe the token, list the chats the bot can see,
and resolve a hand-typed ``@public_name``.

The three pre-channel routes take the token in the body because no row exists
yet — they touch no DB, mirroring the Zalo ``/qr/*` routes. Auth still applies:
the router is registered under ``session_routes``. Everything else about a
telegram channel (list / get / update / delete / test / send) goes through the
generic ``/api/notifications/*`` routes; unlike Zalo the config is fully
client-known, so creation needs no endpoint here.
"""

from __future__ import annotations

from fastapi import Request
from kactus_common.audit import audit
from kactus_common.authorization.const import PermissionAct
from kactus_common.authorization.decorator import permission
from kactus_common.exceptions import ConflictError, ValidationError
from kactus_common.project.const import ProjectPermission
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import MessageResponse, Pagination
from kactus_fin.dependencies import provide_session
from kactus_fin.notification.api import _to_schema
from kactus_notification.channels.telegram.client import (
    TEST_GREETING,
    TEST_MESSAGE_TITLE,
    discover_chats,
    resolve_chat,
    verify_bot,
)
from kactus_notification.channels.telegram.schema import (
    TelegramBotInfo,
    TelegramChannelConfig,
    TelegramChat,
    TelegramChatUpdateRequest,
    TelegramDiscoverRequest,
    TelegramReauthRequest,
    TelegramResolveChatRequest,
    TelegramVerifyRequest,
)
from kactus_notification.const import NotificationChannelType, NotificationTrigger
from kactus_notification.dispatcher import Notifier
from kactus_notification.model import NotificationChannel
from kactus_notification.schema import NotificationChannelSchema, NotificationEvent
from kactus_notification.service import NotificationChannelService
from sqlalchemy.ext.asyncio import AsyncSession

telegram_router = KactusAPIRouter(
    prefix="/api/notifications/telegram", tags=["notifications", "telegram"]
)


# --------------------------------------------------------------------------- #
# Pre-channel setup (token in the body; nothing stored)
# --------------------------------------------------------------------------- #
@telegram_router.post("/verify")
async def telegram_verify(
    body: TelegramVerifyRequest, request: Request
) -> TelegramBotInfo:
    """Probe a bot token before a channel is created (``getMe``).

    Catches a bad token at the form instead of leaving a dead channel row behind
    for the generic ``/{id}/test`` to discover later.
    """
    return await verify_bot(body.bot_token)


@telegram_router.post("/chats")
async def telegram_chats(
    body: TelegramDiscoverRequest, request: Request
) -> Pagination[TelegramChat]:
    """Chats this bot can see — the chat-id finder.

    An empty list is a normal answer, not a failure: the bot only receives a
    ``channel_post`` update once it is an administrator *and* something has been
    posted since (Telegram also drops updates older than 24h). The client shows
    the "add the bot as admin, then post" guide for that case.
    """
    chats = await discover_chats(body.bot_token)
    return Pagination(total=len(chats), items=chats)


@telegram_router.post("/chats/resolve")
async def telegram_resolve_chat(
    body: TelegramResolveChatRequest, request: Request
) -> TelegramChat:
    """Resolve a typed chat id or ``@public_name`` (``getChat``)."""
    return await resolve_chat(body.bot_token, body.chat_id)


# --------------------------------------------------------------------------- #
# Existing channel — the stored token is used; no secret crosses the wire
# --------------------------------------------------------------------------- #
def _require_telegram(channel: NotificationChannel) -> None:
    """These routes touch telegram-shaped config — reject any other type."""
    if (
        NotificationChannelType(channel.channel_type)
        != NotificationChannelType.TELEGRAM
    ):
        raise ValidationError("Not a Telegram channel")


def _telegram_config(channel: NotificationChannel) -> TelegramChannelConfig:
    """Parse the stored (already-decrypted) config."""
    return TelegramChannelConfig.model_validate(channel.config or {})


@telegram_router.get("/channels/{channel_id}/chats")
@permission(ProjectPermission.project, PermissionAct.read)
@provide_session
async def telegram_channel_chats(
    channel_id: int,
    request: Request,
    session: AsyncSession,
) -> Pagination[TelegramChat]:
    """Chats reachable with the channel's **stored** token (the re-pick picker).

    The client cannot supply the token here — reads come back masked as ``***`` —
    so changing the target chat never re-sends a secret.
    """
    channel = await NotificationChannelService.get_or_404(session, channel_id)
    _require_telegram(channel)
    cfg = _telegram_config(channel)
    chats = await discover_chats(cfg.bot_token, cfg.timeout)
    return Pagination(total=len(chats), items=chats)


@telegram_router.put("/channels/{channel_id}/chat")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def telegram_update_chat(
    channel_id: int,
    body: TelegramChatUpdateRequest,
    request: Request,
    session: AsyncSession,
) -> NotificationChannelSchema:
    """Repoint the channel at a different chat — server-side merge.

    Only ``chat_id`` is accepted; every other field is carried over from the
    stored config. The masked config from the API must never round-trip back
    here, or ``bot_token`` would be overwritten with ``***``.
    """
    channel = await NotificationChannelService.get_or_404(session, channel_id)
    _require_telegram(channel)
    new_config = {**(channel.config or {}), "chat_id": body.chat_id}
    channel = await NotificationChannelService.update(
        session, channel, config=new_config
    )
    audit(
        "notification.channel.update_chat",
        "notification_channel",
        channel.id,
        meta={"chat_id": body.chat_id},
    )
    return _to_schema(channel)


@telegram_router.post("/channels/{channel_id}/test-message")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def telegram_test_message(
    channel_id: int,
    request: Request,
    session: AsyncSession,
) -> MessageResponse:
    """Send a real message to the configured chat (the ⚡ button).

    The generic ``/test`` only calls ``getMe``: it proves the token is alive but
    says nothing about whether the bot can post to *this* chat. The usual failure
    — bot not an admin, or missing "Post messages" — is invisible until a real
    send, which is what this does.

    Synchronous on purpose (mirror of Zalo's ⚡): the user is waiting for the
    outcome. Blocked on an inactive channel — a greeting is a real message, and
    deactivate must mean silence. ``Notifier.send_event`` records it in the send
    history like any other delivery.
    """
    channel = await NotificationChannelService.get_or_404(session, channel_id)
    _require_telegram(channel)
    if not channel.is_active:
        raise ConflictError("Channel is inactive — activate it before testing")
    await Notifier.send_event(
        session,
        channel,
        NotificationEvent(title=TEST_MESSAGE_TITLE, body=TEST_GREETING),
        trigger=NotificationTrigger.TEST,
    )
    await NotificationChannelService.mark_used(session, channel)
    audit("notification.channel.test_message", "notification_channel", channel.id)
    return MessageResponse(message="ok")


@telegram_router.put("/channels/{channel_id}/reauth")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def telegram_reauth_channel(
    channel_id: int,
    body: TelegramReauthRequest,
    request: Request,
    session: AsyncSession,
) -> NotificationChannelSchema:
    """Swap in a fresh bot token, keeping the target chat.

    @BotFather can revoke and reissue a token, which kills an otherwise correct
    channel — this is the Telegram equivalent of Zalo's QR re-auth. The new token
    is probed with ``getMe`` **before** it is stored, so a typo cannot replace a
    working credential with a dead one.
    """
    channel = await NotificationChannelService.get_or_404(session, channel_id)
    _require_telegram(channel)
    bot = await verify_bot(body.bot_token)
    new_config = {**(channel.config or {}), "bot_token": body.bot_token}
    channel = await NotificationChannelService.update(
        session, channel, config=new_config
    )
    audit(
        "notification.channel.reauth",
        "notification_channel",
        channel.id,
        meta={"channel_type": "telegram", "bot": bot.username},
    )
    return _to_schema(channel)
