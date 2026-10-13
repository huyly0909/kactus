"""Zalo PA config + the shapes the QR-onboarding endpoints speak."""

from __future__ import annotations

from kactus_common.schemas import BaseSchema
from pydantic import Field, model_validator

from ...schema import BaseChannelConfig, Recipient


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
    the ``EncryptedJSON`` config column, masked in API responses). Legacy single-target
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


# --------------------------------------------------------------------------- #
# QR login onboarding (channel-specific request/response shapes)
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
    thread_type: int = 0
    name: str | None = None
    ok: bool
    error: str | None = None


class ZaloPATestMessageResponse(BaseSchema):
    """Outcome of sending the test greeting to every saved conversation."""

    sent: int
    failed: int
    results: list[ZaloPATestMessageResult] = []
