"""The ``X-Service-Token`` guard on ``/internal``.

The data plane is not routed from the internet — compose keeps it on the
internal network and stag/prod publish no port. This token is the second lock,
for the case where something else lands on that network.
"""

from __future__ import annotations

import pytest
from kactus_common.exceptions import ConfigurationError, PermissionDeniedError
from kactus_data_server.security import require_service_token

INTERNAL_ROUTES = [
    ("GET", "/internal/market/gold"),
    ("GET", "/internal/market/stocks"),
    ("GET", "/internal/market/stocks/FPT"),
    ("GET", "/internal/assets/STOCK/quotes"),
    ("GET", "/internal/scheduler/status"),
    ("POST", "/internal/crawl"),
    ("POST", "/internal/catalog/sync"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", INTERNAL_ROUTES)
async def test_every_internal_route_requires_the_token(anon_client, method, path):
    """Enumerated rather than spot-checked: the guard is per-router, so a new
    router added without ``dependencies=[Depends(require_service_token)]`` is
    open and nothing else would notice."""
    resp = await anon_client.request(method, path, json={})
    assert resp.status_code == 403, path
    assert resp.json()["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_wrong_token_is_rejected(app, service_token):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Service-Token": service_token + "x"},
    ) as c:
        resp = await c.get("/internal/market/gold")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_correct_token_is_accepted(client):
    assert (await client.get("/internal/market/gold")).status_code == 200


@pytest.mark.asyncio
async def test_health_needs_no_token(anon_client):
    """Compose's ``condition: service_healthy`` probe holds no secret."""
    resp = await anon_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["duckdb"] == "ok"


@pytest.mark.asyncio
async def test_unset_secret_fails_closed(app, monkeypatch):
    """An empty configured secret must not make the whole surface anonymous.

    ``compare_digest("", "")`` is True, so waving the request through on an
    unset token would open ``/internal`` to everything on the network — the
    exact failure this guard exists to prevent, and one that looks like a
    working deployment.
    """
    from kactus_common import config as config_mod

    monkeypatch.setattr(
        config_mod.settings, "internal_service_token", "", raising=False
    )
    with pytest.raises(ConfigurationError):
        await require_service_token("")


@pytest.mark.asyncio
async def test_guard_rejects_empty_header_when_secret_is_set(app):
    with pytest.raises(PermissionDeniedError):
        await require_service_token("")
