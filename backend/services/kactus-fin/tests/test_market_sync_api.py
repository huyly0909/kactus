"""``/api/market/gold/{backfill,sync}`` + ``/api/market/sync/jobs`` — the
superuser-only sync-job queue surface owned by kactus-fin.

Unlike the market *reads* (which forward to the data plane), enqueue is a plain
Postgres insert here: ``created_by`` auto-populates from the request user, the
partial unique index collapses duplicate clicks, and the single data-plane
dispatcher — not exercised in this process — later claims the row. So these
tests hit a real (SQLite) DB through ``SyncJobService`` and assert the queue
rows, the min-date clamp, the dedup, and the superuser gate.

``SyncJob`` is imported at module load so ``Base.metadata.create_all`` builds the
``sync_jobs`` table for the in-memory DB.
"""

from __future__ import annotations

import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.sync.const import SyncJobStatus
from kactus_common.sync.model import SyncJob  # noqa: F401 — register on Base.metadata
from kactus_common.user import auth as auth_mod
from kactus_common.user.model import User
from kactus_gold.sync import GOLD_BACKFILL_MIN

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


@pytest_asyncio.fixture
async def finished(db):
    """Two finished runs of one type plus one of another, and a live job.

    The live job must not appear: the scheduler view asks "how did the last run
    go", and a job that has not finished has no answer yet.
    """
    rows = [
        ("stock_quotes", SyncJobStatus.FAILED, datetime.date(2026, 7, 1)),
        ("stock_quotes", SyncJobStatus.SUCCESS, datetime.date(2026, 7, 2)),
        ("gold_quotes", SyncJobStatus.SUCCESS, datetime.date(2026, 7, 3)),
        ("stock_ohlcv", SyncJobStatus.RUNNING, None),
    ]
    async with db.get_session() as session:
        for i, (job_type, status, day) in enumerate(rows):
            session.add(
                SyncJob.init(
                    job_type=job_type,
                    dedup_key=f"{job_type}:{i}",
                    params={},
                    status=str(status),
                    finished_at=(
                        datetime.datetime.combine(
                            day, datetime.time(12, 0), tzinfo=datetime.UTC
                        )
                        if day
                        else None
                    ),
                )
            )
        await session.commit()


@pytest.mark.asyncio
async def test_latest_returns_one_finished_job_per_type(admin_client, finished):
    resp = await admin_client.get("/api/market/sync/jobs/latest")
    assert resp.status_code == 200
    by_type = {j["job_type"]: j for j in resp.json()["data"]}
    # One row per type, the newer stock_quotes run wins, the live job is absent.
    assert set(by_type) == {"stock_quotes", "gold_quotes"}
    assert by_type["stock_quotes"]["status"] == str(SyncJobStatus.SUCCESS)


@pytest.mark.asyncio
async def test_latest_requires_superuser(user_client):
    resp = await user_client.get("/api/market/sync/jobs/latest")
    assert resp.status_code == 403


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


# --------------------------------------------------------------------------- #
# Search (paged / filtered queue)
# --------------------------------------------------------------------------- #
#: Seed rows for the search tests, oldest → newest. Enqueueing through the API
#: cannot produce this fixture: the dedup index allows only one live job per
#: key, and ``create_time`` would collapse into the same instant.
SEED = [
    ("gold_backfill", "sjc", SyncJobStatus.SUCCESS, datetime.date(2026, 7, 1)),
    ("gold_backfill", "mihong", SyncJobStatus.FAILED, datetime.date(2026, 7, 2)),
    ("gold_sync", "yahoo", SyncJobStatus.SUCCESS, datetime.date(2026, 7, 3)),
    ("gold_sync", "sjc", SyncJobStatus.CANCELLED, datetime.date(2026, 7, 4)),
    ("stock_sync", "vnstock", SyncJobStatus.SUCCESS, datetime.date(2026, 7, 5)),
    ("gold_backfill", "yahoo", SyncJobStatus.PENDING, datetime.date(2026, 7, 6)),
    ("gold_sync", "mihong", SyncJobStatus.RUNNING, datetime.date(2026, 7, 7)),
]


@pytest_asyncio.fixture
async def seeded(db):
    """Insert {@link SEED} at 12:00 UTC on each day, oldest first."""
    async with db.get_session() as session:
        for i, (job_type, source, status, day) in enumerate(SEED):
            session.add(
                SyncJob.init(
                    job_type=job_type,
                    dedup_key=f"{job_type}:{source}:{i}",
                    params={"source": source},
                    status=str(status),
                    create_time=datetime.datetime.combine(
                        day, datetime.time(12, 0), tzinfo=datetime.UTC
                    ),
                )
            )
        await session.commit()
    return SEED


def _sources(resp) -> list[str]:
    return [j["params"]["source"] for j in resp.json()["data"]["items"]]


@pytest.mark.asyncio
async def test_search_requires_superuser(user_client):
    resp = await user_client.get("/api/market/sync/jobs/search")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_search_defaults_to_newest_first_all_statuses(admin_client, seeded):
    resp = await admin_client.get("/api/market/sync/jobs/search")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == len(SEED)
    assert data["page"] == 1
    # Newest first, and no status is filtered out by default.
    assert _sources(resp) == [s for _, s, _, _ in reversed(SEED)]


@pytest.mark.asyncio
async def test_search_order_asc_flips_the_page(admin_client, seeded):
    resp = await admin_client.get(
        "/api/market/sync/jobs/search", params={"order": "asc"}
    )
    assert _sources(resp) == [s for _, s, _, _ in SEED]


@pytest.mark.asyncio
async def test_search_pages_without_gaps_or_repeats(admin_client, seeded):
    seen: list[str] = []
    for page in (1, 2, 3, 4):
        resp = await admin_client.get(
            "/api/market/sync/jobs/search", params={"page": page, "page_size": 2}
        )
        body = resp.json()["data"]
        assert body["total"] == len(SEED)  # total is the match count, not the page
        assert body["page_size"] == 2
        seen.extend(_sources(resp))
    # Walking every page reproduces the full ordering exactly — no row dropped
    # at a page boundary, none served twice.
    assert seen == [s for _, s, _, _ in reversed(SEED)]


@pytest.mark.asyncio
async def test_search_status_active_matches_pending_and_running(admin_client, seeded):
    resp = await admin_client.get(
        "/api/market/sync/jobs/search", params={"status": "active"}
    )
    body = resp.json()["data"]
    assert body["total"] == 2
    assert {j["status"] for j in body["items"]} == {
        SyncJobStatus.PENDING,
        SyncJobStatus.RUNNING,
    }


@pytest.mark.asyncio
async def test_search_status_literal_narrows_to_one(admin_client, seeded):
    resp = await admin_client.get(
        "/api/market/sync/jobs/search", params={"status": "failed"}
    )
    body = resp.json()["data"]
    assert body["total"] == 1
    assert body["items"][0]["params"]["source"] == "mihong"


@pytest.mark.asyncio
async def test_search_type_matches_the_job_family(admin_client, seeded):
    """``gold`` covers gold_backfill + gold_sync, and excludes stock_sync."""
    resp = await admin_client.get(
        "/api/market/sync/jobs/search", params={"type": "gold"}
    )
    body = resp.json()["data"]
    assert body["total"] == 6
    assert all(j["job_type"].startswith("gold_") for j in body["items"])


@pytest.mark.asyncio
async def test_search_job_matches_one_exact_job_type(admin_client, seeded):
    """``job`` is the jobs-pane link: the tasks of *this* scheduler job only.

    Narrower than ``type`` on purpose — ``gold_sync`` must not drag in
    ``gold_backfill`` just because they share a family prefix.
    """
    resp = await admin_client.get(
        "/api/market/sync/jobs/search", params={"job": "gold_sync"}
    )
    body = resp.json()["data"]
    assert body["total"] == 3
    assert {j["job_type"] for j in body["items"]} == {"gold_sync"}


@pytest.mark.asyncio
async def test_search_source_filters_on_params_json(admin_client, seeded):
    resp = await admin_client.get(
        "/api/market/sync/jobs/search", params={"source": "mihong"}
    )
    body = resp.json()["data"]
    assert body["total"] == 2
    assert _sources(resp) == ["mihong", "mihong"]


@pytest.mark.asyncio
async def test_search_filters_combine(admin_client, seeded):
    resp = await admin_client.get(
        "/api/market/sync/jobs/search",
        params={"type": "gold", "source": "sjc", "status": "success"},
    )
    body = resp.json()["data"]
    assert body["total"] == 1
    assert body["items"][0]["job_type"] == "gold_backfill"


@pytest.mark.asyncio
async def test_search_date_range_is_inclusive_on_both_ends(admin_client, seeded):
    resp = await admin_client.get(
        "/api/market/sync/jobs/search",
        params={"created_from": "2026-07-02", "created_to": "2026-07-04"},
    )
    body = resp.json()["data"]
    assert body["total"] == 3
    assert _sources(resp) == ["sjc", "yahoo", "mihong"]


@pytest.mark.asyncio
async def test_search_date_range_is_read_in_the_user_timezone(app, db):
    """A job enqueued at 20:00 UTC on 2026-06-30 is 03:00 on 07-01 in VN.

    So asking for "2026-07-01" returns it for a UTC+7 user and not for a UTC
    one: the day the filter cuts on follows the viewer, per the timezone
    convention. Filtering the raw UTC day would put the row on the wrong page
    for every Vietnamese admin — which is the whole product.
    """
    async with db.get_session() as session:
        session.add(
            SyncJob.init(
                job_type="gold_sync",
                dedup_key="gold_sync:tz",
                params={"source": "sjc"},
                status=str(SyncJobStatus.SUCCESS),
                create_time=datetime.datetime(2026, 6, 30, 20, 0, tzinfo=datetime.UTC),
            )
        )
        await session.commit()

    vn = await _login(
        app,
        email="vn@kactus.io",
        password="Admin123!",
        is_superuser=True,
        timezone="Asia/Ho_Chi_Minh",
    )
    utc = await _login(
        app,
        email="utc@kactus.io",
        password="Admin123!",
        is_superuser=True,
        timezone="UTC",
    )
    params = {"created_from": "2026-07-01", "created_to": "2026-07-01"}
    try:
        assert (await vn.get("/api/market/sync/jobs/search", params=params)).json()[
            "data"
        ]["total"] == 1
        assert (await utc.get("/api/market/sync/jobs/search", params=params)).json()[
            "data"
        ]["total"] == 0
    finally:
        await vn.aclose()
        await utc.aclose()


@pytest.mark.asyncio
async def test_search_active_count_is_global_not_page_scoped(admin_client, seeded):
    """The "N running" chip must stay truthful on page 2 of a failed-only view."""
    resp = await admin_client.get(
        "/api/market/sync/jobs/search", params={"status": "failed", "page": 1}
    )
    body = resp.json()["data"]
    assert body["total"] == 1
    assert body["active_count"] == 2

    last = await admin_client.get(
        "/api/market/sync/jobs/search", params={"page": 4, "page_size": 2}
    )
    assert last.json()["data"]["active_count"] == 2


@pytest.mark.asyncio
async def test_search_page_size_is_capped(admin_client):
    assert (
        await admin_client.get(
            "/api/market/sync/jobs/search", params={"page_size": 500}
        )
    ).status_code == 422
    assert (
        await admin_client.get("/api/market/sync/jobs/search", params={"page": 0})
    ).status_code == 422
