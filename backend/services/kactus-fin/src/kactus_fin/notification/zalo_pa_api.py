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
from kactus_common.project.const import ProjectPermission
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import Pagination
from kactus_fin.dependencies import provide_session
from kactus_fin.notification.api import _to_schema
from kactus_notification.const import NotificationChannelType
from kactus_notification.schema import (
    NotificationChannelSchema,
    Recipient,
    ZaloPAChannelCreateRequest,
    ZaloPACompleteResponse,
    ZaloPAQRGenerateResponse,
    ZaloPAQRStatusResponse,
    ZaloPAReauthRequest,
)
from kactus_notification.service import NotificationChannelService
from kactus_notification.zalo_pa import (
    build_channel_config,
    complete_login,
    generate_qr,
    list_session_recipients,
    session_credentials,
    wait_for_confirm,
    wait_for_scan,
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
# Channel create / re-auth (writes the shared NotificationChannel)
# --------------------------------------------------------------------------- #
@zalo_pa_router.post("/channels")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def zalo_create_channel(
    body: ZaloPAChannelCreateRequest,
    request: Request,
    session: AsyncSession,
) -> NotificationChannelSchema:
    """Create a Zalo PA channel from a completed session + chosen recipient."""
    user = request.state.user
    config = await build_channel_config(
        body.session_id,
        thread_id=body.thread_id,
        thread_type=body.thread_type,
        recipient_name=body.recipient_name,
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
        meta={"channel_type": "zalo_pa"},
    )
    return _to_schema(channel)


@zalo_pa_router.put("/channels/{channel_id}/reauth")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def zalo_reauth_channel(
    channel_id: int,
    body: ZaloPAReauthRequest,
    request: Request,
    session: AsyncSession,
) -> NotificationChannelSchema:
    """Refresh a channel's login session after a re-scan (recipient kept)."""
    channel = await NotificationChannelService.get_or_404(session, channel_id)
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
