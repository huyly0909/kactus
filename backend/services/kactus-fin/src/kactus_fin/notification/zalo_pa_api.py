"""Zalo PA onboarding API — QR login, recipient picker, channel create/re-auth.

Credentials are **server-held** (never sent by the client): the QR flow captures
them into an in-process session store, and channel create/re-auth assemble the
``ZaloPAChannelConfig`` server-side. List / get / update / delete / test / **send**
of a zalo_pa channel all go through the generic ``/api/notifications/*`` routes
(shared model + shared ``Notifier``) — only the credential-bearing steps live here.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from kactus_common.audit import audit
from kactus_common.authorization.const import PermissionAct
from kactus_common.authorization.decorator import permission
from kactus_common.database.oltp.models import utcnow
from kactus_common.exceptions import ConflictError, ValidationError
from kactus_common.project.const import ProjectPermission
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import Pagination
from kactus_fin.dependencies import provide_session
from kactus_fin.notification.api import _to_schema
from kactus_notification.channels.zalo_pa.client import (
    TEST_GREETING,
    TEST_MESSAGE_TITLE,
    build_channel_config,
    complete_login,
    generate_qr,
    list_channel_recipients,
    list_session_recipients,
    send_greeting_to_recipients,
    session_credentials,
    wait_for_confirm,
    wait_for_scan,
)
from kactus_notification.channels.zalo_pa.schema import (
    ZaloPAChannelConfig,
    ZaloPAChannelCreateRequest,
    ZaloPACompleteResponse,
    ZaloPAQRGenerateResponse,
    ZaloPAQRStatusResponse,
    ZaloPAReauthRequest,
    ZaloPARecipientsUpdateRequest,
    ZaloPATestMessageResponse,
    ZaloPATestMessageResult,
    ZaloRecipientTarget,
)
from kactus_notification.const import (
    NotificationChannelType,
    NotificationLogStatus,
    NotificationTrigger,
)
from kactus_notification.model import NotificationChannel
from kactus_notification.schema import (
    NotificationChannelSchema,
    NotificationEvent,
    Recipient,
)
from kactus_notification.service import (
    NotificationChannelService,
    NotificationLogService,
)
from sqlalchemy.ext.asyncio import AsyncSession

zalo_pa_router = KactusAPIRouter(
    prefix="/api/notifications/zalo-pa", tags=["notifications", "zalo-pa"]
)


# --------------------------------------------------------------------------- #
# QR login (in-process session store; no DB until a channel is created)
# --------------------------------------------------------------------------- #
@zalo_pa_router.post("/qr/generate")
async def zalo_generate_qr(request: Request) -> ZaloPAQRGenerateResponse:
    """Start a QR login — returns a session handle + the QR to render."""
    session_id = uuid.uuid4().hex
    result = await generate_qr(session_id)
    return ZaloPAQRGenerateResponse(
        session_id=session_id, code=result["code"], image_url=result["image_url"]
    )


@zalo_pa_router.get("/qr/{session_id}/scan")
async def zalo_wait_scan(session_id: str, request: Request) -> ZaloPAQRStatusResponse:
    """Long-poll until the QR is scanned (``refreshed`` = swap image, keep polling)."""
    result = await wait_for_scan(session_id)
    return ZaloPAQRStatusResponse(**result)


@zalo_pa_router.get("/qr/{session_id}/confirm")
async def zalo_wait_confirm(
    session_id: str, request: Request
) -> ZaloPAQRStatusResponse:
    """Long-poll until the user confirms the login on their phone."""
    result = await wait_for_confirm(session_id)
    return ZaloPAQRStatusResponse(**result)


@zalo_pa_router.post("/qr/{session_id}/complete")
async def zalo_complete(session_id: str, request: Request) -> ZaloPACompleteResponse:
    """Finalize login — verify the account and hold the session for recipient pick."""
    result = await complete_login(session_id)
    return ZaloPACompleteResponse(
        session_id=session_id,
        zalo_user_id=result["zalo_user_id"],
        account_name=result["account_name"],
    )


@zalo_pa_router.get("/sessions/{session_id}/recipients")
async def zalo_list_recipients(
    session_id: str, request: Request, query: str = ""
) -> Pagination[Recipient]:
    """Friends + groups of the logged-in account — pick who receives the report."""
    recipients = await list_session_recipients(session_id, query)
    return Pagination(total=len(recipients), items=recipients)


# --------------------------------------------------------------------------- #
# Channel create / re-auth / conversations / test (writes NotificationChannel)
# --------------------------------------------------------------------------- #
_LEGACY_TARGET_KEYS = ("thread_id", "thread_type", "recipient_name")


def _require_zalo(channel: NotificationChannel) -> None:
    """These routes touch zalo-shaped config — reject any other channel type."""
    if NotificationChannelType(channel.channel_type) != NotificationChannelType.ZALO_PA:
        raise ValidationError("Not a Zalo PA channel")


def _zalo_config(channel: NotificationChannel) -> ZaloPAChannelConfig:
    """Parse the stored (already-decrypted) config; legacy scalars are lifted."""
    return ZaloPAChannelConfig.model_validate(channel.config or {})


@zalo_pa_router.post("/channels")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def zalo_create_channel(
    body: ZaloPAChannelCreateRequest,
    request: Request,
    session: AsyncSession,
) -> NotificationChannelSchema:
    """Create a Zalo PA channel from a completed session + chosen conversations."""
    user = request.state.user
    config = await build_channel_config(
        body.session_id,
        recipients=[ZaloRecipientTarget.from_recipient(r) for r in body.recipients],
    )
    channel = await NotificationChannelService.create(
        session,
        owner_id=user.id,
        name=body.name,
        channel_type=NotificationChannelType.ZALO_PA,
        config=config.model_dump(),
    )
    audit(
        "notification.channel.create",
        "notification_channel",
        channel.id,
        meta={"channel_type": "zalo_pa", "recipients": len(body.recipients)},
    )
    return _to_schema(channel)


@zalo_pa_router.get("/channels/{channel_id}/recipients")
@permission(ProjectPermission.project, PermissionAct.read)
@provide_session
async def zalo_channel_recipients(
    channel_id: int,
    request: Request,
    session: AsyncSession,
    query: str = "",
) -> Pagination[Recipient]:
    """Friends + groups reachable with the channel's stored session (edit picker).

    No QR session involved — a dead stored session surfaces as a 502 so the
    client can offer "Reconnect" (re-auth) instead of restarting from scratch.
    """
    channel = await NotificationChannelService.get_or_404(session, channel_id)
    _require_zalo(channel)
    recipients = await list_channel_recipients(_zalo_config(channel), query)
    return Pagination(total=len(recipients), items=recipients)


@zalo_pa_router.put("/channels/{channel_id}/recipients")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def zalo_update_recipients(
    channel_id: int,
    body: ZaloPARecipientsUpdateRequest,
    request: Request,
    session: AsyncSession,
) -> NotificationChannelSchema:
    """Replace the saved conversations — server-side merge, credentials untouched.

    The masked config from the API never round-trips here: only the recipient
    list is accepted, everything else is carried over from the stored config
    (which also normalizes away the legacy scalar target keys).
    """
    channel = await NotificationChannelService.get_or_404(session, channel_id)
    _require_zalo(channel)
    targets = [ZaloRecipientTarget.from_recipient(r) for r in body.recipients]
    new_config = {
        k: v for k, v in (channel.config or {}).items() if k not in _LEGACY_TARGET_KEYS
    }
    new_config["recipients"] = [t.model_dump() for t in targets]
    channel = await NotificationChannelService.update(
        session, channel, config=new_config
    )
    audit(
        "notification.channel.update_recipients",
        "notification_channel",
        channel.id,
        meta={"recipients": len(targets)},
    )
    return _to_schema(channel)


@zalo_pa_router.post("/channels/{channel_id}/test-message")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def zalo_test_message(
    channel_id: int,
    request: Request,
    session: AsyncSession,
) -> ZaloPATestMessageResponse:
    """Send the test greeting to every saved conversation (the ⚡ button).

    Synchronous on purpose (mirror of the generic ``/test``): the user is
    waiting at the UI for the outcome. Blocked on an inactive channel — the
    greeting is a real message, and deactivate must mean silence.

    A real message went out, so it is recorded in the send history like any
    other — ``trigger=test``, with the per-conversation outcome this endpoint
    already computes.
    """
    channel = await NotificationChannelService.get_or_404(session, channel_id)
    _require_zalo(channel)
    if not channel.is_active:
        raise ConflictError("Channel is inactive — activate it before testing")
    results = await send_greeting_to_recipients(_zalo_config(channel), TEST_GREETING)
    sent = sum(1 for r in results if r["ok"])
    failed = [r["error"] for r in results if not r["ok"] and r.get("error")]
    await NotificationLogService.record(
        session,
        channel=channel,
        event=NotificationEvent(title=TEST_MESSAGE_TITLE, body=TEST_GREETING),
        status=(
            NotificationLogStatus.SUCCESS if sent else NotificationLogStatus.FAILED
        ),
        attempts=1,
        # The per-target errors carry the detail; this is the one-line summary.
        error=None if sent else (failed[0] if failed else "No conversation reachable"),
        trigger=NotificationTrigger.TEST,
        finished_at=utcnow(),
        targets=results,
    )
    if sent:
        await NotificationChannelService.mark_used(session, channel)
    audit(
        "notification.channel.test_message",
        "notification_channel",
        channel.id,
        meta={"sent": sent, "failed": len(results) - sent},
    )
    return ZaloPATestMessageResponse(
        sent=sent,
        failed=len(results) - sent,
        results=[ZaloPATestMessageResult(**r) for r in results],
    )


@zalo_pa_router.put("/channels/{channel_id}/reauth")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def zalo_reauth_channel(
    channel_id: int,
    body: ZaloPAReauthRequest,
    request: Request,
    session: AsyncSession,
) -> NotificationChannelSchema:
    """Refresh a channel's login session after a re-scan (recipients kept)."""
    channel = await NotificationChannelService.get_or_404(session, channel_id)
    _require_zalo(channel)
    creds = await session_credentials(body.session_id)
    # Keep the existing recipient + display; swap only the session-credential fields.
    new_config = {
        **(channel.config or {}),
        "cookies": creds["cookies"],
        "imei": creds["imei"],
        "zpw_sek": creds.get("zpw_sek", ""),
        "zpsid": creds.get("zpsid", ""),
        "secret_key": creds.get("secret_key", ""),
        "user_agent": creds["user_agent"],
    }
    channel = await NotificationChannelService.update(
        session, channel, config=new_config
    )
    return _to_schema(channel)
