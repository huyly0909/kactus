"""Notification request/response + per-type config schemas + the neutral event.

Two registries make the feature generic:

* ``CHANNEL_CONFIG_SCHEMAS[type]`` — the Pydantic schema a channel's ``config``
  dict is validated against (base + per-type extension; "load đúng loại").
* ``SECRET_FIELDS[type]``          — config keys masked before leaving the API.

The channel/template *behaviour* registries live in the sibling ``registry``
module (they do I/O); these *data-shape* registries stay here so the persistence
service, the channel impls, and the API masking all share one source of truth.
"""

from __future__ import annotations

import datetime

from kactus_common.schemas import BaseSchema, FancyInt
from pydantic import Field, model_validator

from .const import (
    NotificationChannelType,
    NotificationLevel,
    NotificationLogStatus,
    NotificationTrigger,
)

# --------------------------------------------------------------------------- #
# Per-type config: one base schema, each channel type extends it.
# --------------------------------------------------------------------------- #


class BaseChannelConfig(BaseSchema):
    """Fields common to every channel config."""

    timeout: float = 10.0  # HTTP timeout (seconds) for the outbound transport


class TelegramChannelConfig(BaseChannelConfig):
    """Telegram Bot API config — token + target chat."""

    bot_token: str
    chat_id: str
    parse_mode: str = "HTML"  # HTML | MarkdownV2 | Markdown


class SlackChannelConfig(BaseChannelConfig):
    """Slack Incoming Webhook config."""

    webhook_url: str


class ZaloRecipientTarget(BaseSchema):
    """One saved conversation (send target) on a Zalo PA channel.

    ``thread_type`` follows zlapi: 0 = user (friend), 1 = group. ``name`` and
    ``avatar`` are display snapshots taken at pick time — the live values come
    from the recipients endpoints, so staleness here is cosmetic only.
    """

    thread_id: str
    thread_type: int = 0  # 0 = user, 1 = group
    name: str | None = None
    avatar: str | None = None

    @classmethod
    def from_recipient(cls, recipient: Recipient) -> ZaloRecipientTarget:
        """Map a picker ``Recipient`` (id / is_group) to the stored target shape."""
        return cls(
            thread_id=recipient.id,
            thread_type=1 if recipient.is_group else 0,
            name=recipient.name or None,
            avatar=recipient.avatar,
        )


class ZaloPAChannelConfig(BaseChannelConfig):
    """Zalo Personal Account config — login session **and** chosen conversations.

    Everything here is filled by the QR-login onboarding + conversation picker,
    never typed by hand. The session fields are secrets (encrypted at rest via
    the ``EncryptedJSON`` column, masked in API responses). Legacy single-target
    configs (scalar ``thread_id``/``thread_type``/``recipient_name``) are lifted
    into ``recipients`` on validation — pre-existing rows keep working with no
    migration (the config lives in a JSON column).
    """

    # --- login session (captured by QR login; secret) ---
    cookies: dict = {}
    imei: str  # device id (Zalo ``zpdid`` cookie)
    zpw_sek: str = ""
    zpsid: str = ""
    secret_key: str = ""
    user_agent: str

    # --- conversations (picked from friends/groups) ---
    recipients: list[ZaloRecipientTarget] = []

    # --- display metadata (the logged-in account) ---
    zalo_user_id: str | None = None
    account_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _lift_legacy_recipient(cls, data: object) -> object:
        """Fold a pre-multi-recipient scalar target into ``recipients``."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        thread_id = data.pop("thread_id", None)
        thread_type = data.pop("thread_type", 0)
        recipient_name = data.pop("recipient_name", None)
        if thread_id and not data.get("recipients"):
            data["recipients"] = [
                {
                    "thread_id": thread_id,
                    "thread_type": thread_type,
                    "name": recipient_name,
                }
            ]
        return data


CHANNEL_CONFIG_SCHEMAS: dict[NotificationChannelType, type[BaseChannelConfig]] = {
    NotificationChannelType.TELEGRAM: TelegramChannelConfig,
    NotificationChannelType.SLACK: SlackChannelConfig,
    NotificationChannelType.ZALO_PA: ZaloPAChannelConfig,
}

# Config keys that hold secrets — masked in API responses, encrypted at rest.
SECRET_FIELDS: dict[NotificationChannelType, set[str]] = {
    NotificationChannelType.TELEGRAM: {"bot_token"},
    NotificationChannelType.SLACK: {"webhook_url"},
    NotificationChannelType.ZALO_PA: {
        "cookies",
        "imei",
        "zpw_sek",
        "zpsid",
        "secret_key",
    },
}

SECRET_MASK = "***"


def parse_channel_config(
    channel_type: NotificationChannelType, config: dict
) -> BaseChannelConfig:
    """Validate a raw config dict against its per-type schema.

    Raises ``pydantic.ValidationError`` on a bad/incomplete config — callers
    translate that into a 400 ``ValidationError`` (see the API/service layer).
    """
    return CHANNEL_CONFIG_SCHEMAS[channel_type].model_validate(config or {})


def mask_config(channel_type: NotificationChannelType, config: dict) -> dict:
    """Replace secret values with ``***`` for safe display."""
    secret = SECRET_FIELDS.get(channel_type, set())
    return {k: (SECRET_MASK if k in secret else v) for k, v in (config or {}).items()}


# --------------------------------------------------------------------------- #
# API request / response
# --------------------------------------------------------------------------- #


class NotificationChannelSchema(BaseSchema):
    """Public channel info — ``config`` secrets are masked."""

    id: FancyInt
    owner_id: FancyInt
    name: str
    channel_type: NotificationChannelType
    is_active: bool
    config: dict = {}
    last_used_at: datetime.datetime | None = None


class NotificationLogSchema(BaseSchema):
    """One audit row — the final outcome of a :meth:`Notifier.send_event` call."""

    id: FancyInt
    channel_id: FancyInt
    channel_type: NotificationChannelType
    event_title: str
    level: NotificationLevel
    status: NotificationLogStatus
    trigger: NotificationTrigger
    attempts: int
    error: str | None = None
    started_at: datetime.datetime | None = None
    finished_at: datetime.datetime | None = None


class Recipient(BaseSchema):
    """A pickable send target for a channel (Zalo friend / group)."""

    id: str
    name: str
    avatar: str | None = None
    is_group: bool = False


# --------------------------------------------------------------------------- #
# Zalo PA — QR login onboarding (channel-specific request/response shapes)
# --------------------------------------------------------------------------- #


class ZaloPAQRGenerateResponse(BaseSchema):
    """Step 1 — a freshly generated QR to render + a session handle to poll."""

    session_id: str
    code: str
    image_url: str


class ZaloPAQRStatusResponse(BaseSchema):
    """Long-poll result for scan/confirm.

    ``status`` ∈ scanned | confirmed | refreshed | expired | rejected. On
    ``refreshed`` the client swaps to ``image_url``/``code`` and keeps polling.
    """

    status: str
    image_url: str | None = None
    code: str | None = None
    display_name: str | None = None
    avatar: str | None = None


class ZaloPACompleteResponse(BaseSchema):
    """Step 4 — login finalized; the account is ready to pick a recipient."""

    session_id: str
    zalo_user_id: str
    account_name: str | None = None


class ZaloPAChannelCreateRequest(BaseSchema):
    """Create a Zalo PA channel from a completed login session + N conversations."""

    session_id: str
    name: str
    recipients: list[Recipient] = Field(min_length=1)


class ZaloPAReauthRequest(BaseSchema):
    """Refresh a channel's login session after a re-scan (recipients kept)."""

    session_id: str


class ZaloPARecipientsUpdateRequest(BaseSchema):
    """Replace a channel's saved conversations (credentials untouched)."""

    recipients: list[Recipient] = Field(min_length=1)


class ZaloPATestMessageResult(BaseSchema):
    """Per-conversation outcome of a test-message send."""

    thread_id: str
    name: str | None = None
    ok: bool
    error: str | None = None


class ZaloPATestMessageResponse(BaseSchema):
    """Outcome of sending the test greeting to every saved conversation."""

    sent: int
    failed: int
    results: list[ZaloPATestMessageResult] = []


class NotificationChannelCreateRequest(BaseSchema):
    """Create body — ``config`` is validated against ``channel_type``'s schema."""

    name: str
    channel_type: NotificationChannelType
    config: dict


class NotificationChannelUpdateRequest(BaseSchema):
    """Partial update — only provided fields change."""

    name: str | None = None
    is_active: bool | None = None
    config: dict | None = None


# --------------------------------------------------------------------------- #
# Neutral event — "what to notify". Templates render it per channel type.
# --------------------------------------------------------------------------- #


class NotificationEvent(BaseSchema):
    """Channel-agnostic notification payload.

    A template (per channel type) turns this into the concrete message a
    channel can send (Telegram HTML text / Slack Block Kit / …).
    """

    title: str
    body: str = ""
    level: NotificationLevel = NotificationLevel.INFO
    fields: list[tuple[str, str]] = []  # (label, value) rows
    url: str | None = None
