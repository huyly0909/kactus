"""``/api/market/gold/{backfill,sync}`` + ``/api/market/sync/jobs`` — the
superuser-only sync-job queue surface owned by kactus-fin.

Unlike the market *reads* (which forward to the data plane), enqueue is a plain
Postgres insert here: ``created_by`` auto-populates from the request user, the
partial unique index collapses duplicate clicks, and the single data-server
dispatcher — not exercised in this process — later claims the row. So these
tests hit a real (SQLite) DB through ``SyncJobService`` and assert the queue
rows, the min-date clamp, the dedup, and the superuser gate.

``SyncJob`` is imported at module load so ``Base.metadata.create_all`` builds the
``sync_jobs`` table for the in-memory DB.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.sync.const import SyncJobStatus
from kactus_common.sync.gold import GOLD_BACKFILL_MIN
from kactus_common.sync.model import SyncJob  # noqa: F401 — register on Base.metadata
from kactus_common.user import auth as auth_mod
from kactus_common.user.model import User

TEST_DB_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def db():
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()


@pytest_asyncio.fixture
async def app(db):
    from kactus_common.config import clear_settings, register_settings
    from kactus_fin.app import create_app
    from kactus_fin.config import Settings

    register_settings(Settings(internal_service_token="test-token"))
    session_mod._db = db
    auth_mod._auth = None

    yield create_app()

    session_mod._db = None
    auth_mod._auth = None
    clear_settings()


async def _login(app, *, email: str, password: str, **init) -> AsyncClient:
    async with (await _db_of(app)).get_session() as session:
        session.add(
            User.init(
                email=email,
                username=email.split("@")[0],
                password_hash=password,
                name=email.split("@")[0].title(),
                status="active",
                **init,
            )
        )
        await session.commit()
    transport = ASGITransport(app=app)
    c = AsyncClient(transport=transport, base_url="http://test")
    login = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    c.cookies.update(dict(login.cookies))
    return c


async def _db_of(app) -> DatabaseSessionManager:
    return session_mod._db


@pytest_asyncio.fixture
async def admin_client(app):
    c = await _login(
        app, email="admin@kactus.io", password="Admin123!", is_superuser=True
    )
    yield c
    await c.aclose()


@pytest_asyncio.fixture
async def user_client(app):
    c = await _login(app, email="trader@kactus.io", password="Test123!")
    yield c
    await c.aclose()


async def _jobs(db) -> list[SyncJob]:
    from sqlalchemy import select

    async with db.get_session() as session:
        return list((await session.scalars(select(SyncJob))).all())


# --------------------------------------------------------------------------- #
# Access
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_backfill_requires_superuser(user_client):
    resp = await user_client.post(
        "/api/market/gold/backfill",
        json={"source": "sjc", "date_from": "2020-01-01", "date_to": "2020-02-01"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sync_requires_superuser(user_client):
    resp = await user_client.post("/api/market/gold/sync", json={"source": "all"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_requires_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/market/sync/jobs")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# Enqueue
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_enqueue_backfill_creates_pending_job(admin_client, db):
    resp = await admin_client.post(
        "/api/market/gold/backfill",
        json={"source": "sjc", "date_from": "2015-01-01", "date_to": "2015-06-01"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["created"] is True
    job = body["job"]
    assert job["job_type"] == "gold_backfill"
    assert job["dedup_key"] == "gold_backfill:sjc"
    assert job["status"] == SyncJobStatus.PENDING
    assert job["params"]["date_from"] == "2015-01-01"
    assert job["params"]["date_to"] == "2015-06-01"

    rows = await _jobs(db)
    assert len(rows) == 1
    # created_by auto-populated from the request user (AuditMixin ContextVar).
    assert rows[0].created_by is not None


@pytest.mark.asyncio
async def test_backfill_clamps_date_from_up_to_source_min(admin_client):
    """A below-min start is clamped so no empty windows are ever fetched."""
    resp = await admin_client.post(
        "/api/market/gold/backfill",
        json={"source": "sjc", "date_from": "1990-01-01", "date_to": "2012-01-01"},
    )
    assert resp.status_code == 200
    params = resp.json()["data"]["job"]["params"]
    assert params["date_from"] == GOLD_BACKFILL_MIN["sjc"].isoformat()  # 2009-07-22


@pytest.mark.asyncio
async def test_backfill_range_entirely_before_min_is_400(admin_client):
    resp = await admin_client.post(
        "/api/market/gold/backfill",
        json={"source": "sjc", "date_from": "1990-01-01", "date_to": "1995-01-01"},
    )
    assert resp.status_code == 400
    assert "earliest" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_backfill_reversed_range_is_422(admin_client):
    """date_from after date_to is a schema-level rejection (never enqueued)."""
    resp = await admin_client.post(
        "/api/market/gold/backfill",
        json={"source": "sjc", "date_from": "2020-06-01", "date_to": "2020-01-01"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_backfill_unknown_source_is_422(admin_client):
    resp = await admin_client.post(
        "/api/market/gold/backfill",
        json={"source": "doji", "date_from": "2020-01-01", "date_to": "2020-02-01"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_backfill_mihong_code_in_dedup_key(admin_client):
    resp = await admin_client.post(
        "/api/market/gold/backfill",
        json={
            "source": "mihong",
            "code": "999",
            "date_from": "2026-01-01",
            "date_to": "2026-07-01",
        },
    )
    assert resp.status_code == 200
    job = resp.json()["data"]["job"]
    assert job["dedup_key"] == "gold_backfill:mihong:999"
    assert job["params"]["code"] == "999"


@pytest.mark.asyncio
async def test_duplicate_enqueue_is_collapsed(admin_client, db):
    first = await admin_client.post(
        "/api/market/gold/backfill",
        json={"source": "sjc", "date_from": "2015-01-01", "date_to": "2015-06-01"},
    )
    second = await admin_client.post(
        "/api/market/gold/backfill",
        json={"source": "sjc", "date_from": "2016-01-01", "date_to": "2016-06-01"},
    )
    assert first.json()["data"]["created"] is True
    assert second.json()["data"]["created"] is False
    # Same live job returned; the second click did not stack a row.
    assert first.json()["data"]["job"]["id"] == second.json()["data"]["job"]["id"]
    assert len(await _jobs(db)) == 1


@pytest.mark.asyncio
async def test_enqueue_sync_all(admin_client):
    resp = await admin_client.post("/api/market/gold/sync", json={"source": "all"})
    assert resp.status_code == 200
    job = resp.json()["data"]["job"]
    assert job["job_type"] == "gold_sync"
    assert job["dedup_key"] == "gold_sync:all"
    assert job["params"] == {"source": "all"}


@pytest.mark.asyncio
async def test_enqueue_sync_defaults_source_to_all(admin_client):
    resp = await admin_client.post("/api/market/gold/sync", json={})
    assert resp.status_code == 200
    assert resp.json()["data"]["job"]["dedup_key"] == "gold_sync:all"


# --------------------------------------------------------------------------- #
# List + cancel
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_jobs_returns_active_and_recent(admin_client):
    await admin_client.post(
        "/api/market/gold/backfill",
        json={"source": "sjc", "date_from": "2015-01-01", "date_to": "2015-06-01"},
    )
    await admin_client.post("/api/market/gold/sync", json={"source": "yahoo"})

    resp = await admin_client.get("/api/market/sync/jobs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Both are live; active is FIFO (backfill enqueued first).
    assert [j["job_type"] for j in data["active"]] == ["gold_backfill", "gold_sync"]
    assert len(data["recent"]) == 2


@pytest.mark.asyncio
async def test_cancel_job_marks_cancelled(admin_client):
    enq = await admin_client.post("/api/market/gold/sync", json={"source": "sjc"})
    job_id = enq.json()["data"]["job"]["id"]

    resp = await admin_client.post(f"/api/market/sync/jobs/{job_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == SyncJobStatus.CANCELLED

    # Cancelling frees the dedup slot — the same source can be enqueued again.
    again = await admin_client.post("/api/market/gold/sync", json={"source": "sjc"})
    assert again.json()["data"]["created"] is True


@pytest.mark.asyncio
async def test_cancel_unknown_job_is_404(admin_client):
    resp = await admin_client.post("/api/market/sync/jobs/999999/cancel")
    assert resp.status_code == 404
