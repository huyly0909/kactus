"""Swagger UI that can call CSRF-protected routes.

Swagger UI only sends the headers an operation declares, so after the CSRF check
every unsafe "Try it out" on a session route came back 403. This page is
FastAPI's own ``/docs`` plus one ``requestInterceptor`` that does what axios does
in the SPA: copy the ``kactus_xsrf_token`` cookie into ``X-XSRF-TOKEN`` on
same-origin requests.

No new hole: the page is served from this origin, and only this origin's
scripts can read that cookie — the same position the SPA is in.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from kactus_common.user.const import CSRF_COOKIE_NAME, CSRF_HEADER_NAME

router = APIRouter(include_in_schema=False)

_BUNDLE_CALL = "SwaggerUIBundle({"

_CSRF_INTERCEPTOR = f"""
    requestInterceptor: (req) => {{
        const name = {json.dumps(CSRF_COOKIE_NAME)} + '=';
        const pair = document.cookie.split('; ').find((c) => c.startsWith(name));
        const sameOrigin = new URL(req.url, location.href).origin === location.origin;
        if (pair && sameOrigin) {{
            req.headers[{json.dumps(CSRF_HEADER_NAME)}] =
                decodeURIComponent(pair.slice(name.length));
        }}
        return req;
    }},"""


@router.get("/docs")
async def swagger_ui(request: Request) -> HTMLResponse:
    page = get_swagger_ui_html(
        openapi_url=request.app.openapi_url,
        title=f"{request.app.title} - Swagger UI",
    )
    html = bytes(page.body).decode()
    # Fails loudly (and in test_csrf.py) if FastAPI ever changes its template,
    # rather than silently serving a Swagger that 403s on every write.
    if _BUNDLE_CALL not in html:
        raise RuntimeError("FastAPI Swagger template changed; CSRF hook not injected")
    return HTMLResponse(html.replace(_BUNDLE_CALL, _BUNDLE_CALL + _CSRF_INTERCEPTOR, 1))
