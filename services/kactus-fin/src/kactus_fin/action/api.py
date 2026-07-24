"""Action links — ``GET`` shows, ``POST`` does.

⚠️ **The split is the security control, not a UX nicety.**  Telegram, Slack and
Zalo all fetch a URL as soon as it appears in a message, to render a preview.
Nobody clicked anything.  If ``GET`` executed, every actionable notification
would fire the moment it was delivered — silently, correctly authenticated, and
attributed to the user.  So ``GET`` renders a confirmation page and touches
nothing; only the ``POST`` that page submits consumes the token.

That is also why the route returns HTML rather than the usual JSON envelope: the
audience is a browser opened from a chat app, not the SPA.

Both verbs require a session.  The token is a *pre-authorisation*, not a
credential — anyone who ends up holding the link (forwarded message, group chat,
shoulder surf) still has to be signed in as the user it was issued for.
"""

from __future__ import annotations

import html

from fastapi import Request
from fastapi.responses import HTMLResponse
from kactus_common.router import KactusAPIRouter
from kactus_fin.dependencies import provide_session
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from .const import ACTION_LABELS, ActionType
from .model import ActionToken
from .schema import ActionIssueRequest, ActionLinkSchema
from .service import ActionTokenService

router = KactusAPIRouter(prefix="/api/actions", tags=["actions"])


def _page(title: str, body: str, *, status_code: int = 200) -> HTMLResponse:
    """One tiny self-contained page — no assets, no JS framework, no CDN.

    This is reached from an external app's in-app browser, often on a phone with
    a bad connection; a page that needs to load anything else is a page that
    sometimes does not load.
    """
    return HTMLResponse(
        status_code=status_code,
        content=(
            "<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Kactus</title><style>"
            "body{font-family:system-ui,-apple-system,sans-serif;margin:0;"
            "min-height:100vh;display:flex;align-items:center;"
            "justify-content:center;background:#0b1220;color:#e6edf3}"
            ".card{max-width:26rem;padding:2rem;background:#131c2e;"
            "border-radius:.75rem;box-shadow:0 1px 3px rgba(0,0,0,.4)}"
            "h1{font-size:1.15rem;margin:0 0 .75rem}"
            "dl{margin:1rem 0;font-size:.9rem}dt{color:#8b98a9;float:left;"
            "clear:left;width:8rem}dd{margin:0 0 .35rem 8rem}"
            "button{width:100%;padding:.75rem;font-size:1rem;border:0;"
            "border-radius:.5rem;background:#2f81f7;color:#fff;cursor:pointer}"
            "p{color:#8b98a9;font-size:.85rem;line-height:1.5}"
            "</style></head><body><div class='card'>"
            f"<h1>{title}</h1>{body}</div></body></html>"
        ),
    )


def _confirmation_page(token: str, row: ActionToken) -> HTMLResponse:
    label = ACTION_LABELS.get(ActionType(row.action), row.action)
    details = "".join(
        f"<dt>{html.escape(str(k))}</dt><dd>{html.escape(str(v))}</dd>"
        for k, v in (row.params or {}).items()
    )
    expires = row.expires_at.strftime("%H:%M %d/%m/%Y")
    return _page(
        html.escape(label),
        f"<dl>{details}</dl>"
        f"<p>This link can be used once and expires at {expires}.</p>"
        f"<form method='post' action='/api/actions/{html.escape(token)}'>"
        "<button type='submit'>Confirm</button></form>",
    )


@router.post("")
@provide_session
async def issue_action(
    body: ActionIssueRequest, request: Request, session: AsyncSession
) -> ActionLinkSchema:
    """Mint a link for the current user, to put in a notification's ``url``.

    Always issued for ``request.state.user`` — never for a user_id in the body.
    A caller who could name the subject could mint a link that runs against
    someone else's portfolio, and the whole scheme rests on the token's user
    being the user who asked for it.
    """
    user = request.state.user
    row, token = await ActionTokenService.issue(
        session,
        user_id=user.id,
        action=body.action,
        params=body.params,
        ttl_secs=body.ttl_secs,
    )
    return ActionLinkSchema(
        id=row.id,
        action=body.action,
        token=token,
        url=ActionTokenService.url_for(token),
        expires_at=row.expires_at,
    )


@router.get("/{token}", response_class=HTMLResponse)
@provide_session
async def show_action(
    token: str, request: Request, session: AsyncSession
) -> HTMLResponse:
    """Render the confirmation page. **Changes nothing.**

    Safe to fetch any number of times — which link previewers absolutely will.
    """
    row = await ActionTokenService.resolve(
        session, token, user_id=request.state.user.id
    )
    return _confirmation_page(token, row)


@router.post("/{token}", response_class=HTMLResponse)
@provide_session
async def run_action(
    token: str, request: Request, session: AsyncSession
) -> HTMLResponse:
    """Consume the token and run the action. The only verb that does anything."""
    user = request.state.user
    row = await ActionTokenService.resolve(session, token, user_id=user.id)
    message = await ActionTokenService.execute(session, row)
    logger.info(f"Action {row.action} executed by user {user.id} via token {row.id}")
    return _page("Done", f"<p>{html.escape(message)}</p>")
