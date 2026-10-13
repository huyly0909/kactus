"""Telegram config + the shapes the setup/discovery endpoints speak."""

from __future__ import annotations

from kactus_common.schemas import BaseSchema

from ...schema import BaseChannelConfig


class TelegramChannelConfig(BaseChannelConfig):
    """Telegram Bot API config — token + target chat."""

    bot_token: str
    chat_id: str
    parse_mode: str = "HTML"  # HTML | MarkdownV2 | Markdown


# --------------------------------------------------------------------------- #
# Setup / chat discovery (channel-specific request/response shapes)
# --------------------------------------------------------------------------- #


class TelegramBotInfo(BaseSchema):
    """``getMe`` — proves the token is live and names the bot for the UI."""

    id: str
    username: str
    first_name: str = ""


class TelegramChat(BaseSchema):
    """A chat the bot can see — the pickable target of a Telegram channel.

    Not modelled as the shared :class:`Recipient`: ``is_group`` cannot tell a
    channel from a group, and that difference is the whole point here (a channel
    needs the bot as admin with *Post messages*; a group does not). ``username``
    also carries the ``@public_name`` form users can type by hand.
    """

    id: str  # "-1001234567890" — channel ids always start with -100
    title: str  # title | username | first+last name
    type: str  # channel | supergroup | group | private
    username: str | None = None


class TelegramVerifyRequest(BaseSchema):
    """Probe a token before any channel row exists."""

    bot_token: str


class TelegramDiscoverRequest(BaseSchema):
    """List the chats a not-yet-saved bot token can see."""

    bot_token: str


class TelegramResolveChatRequest(BaseSchema):
    """Look up one chat by id or ``@username`` (the public-channel shortcut)."""

    bot_token: str
    chat_id: str


class TelegramChatUpdateRequest(BaseSchema):
    """Repoint an existing channel at a different chat (token untouched)."""

    chat_id: str


class TelegramReauthRequest(BaseSchema):
    """Swap in a fresh bot token — the target chat is kept.

    The Telegram counterpart of Zalo's QR re-auth: @BotFather can revoke and
    reissue a token, which kills an otherwise correctly configured channel.
    """

    bot_token: str
