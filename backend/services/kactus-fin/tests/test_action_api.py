"""Signed one-time action links.

The test that matters most is ``test_get_never_consumes_or_executes``. Every
chat platform this project sends to — Telegram, Slack, Zalo — fetches a URL as
soon as it lands in a message, to build a link preview. If ``GET`` executed, an
actionable notification would fire itself on delivery, correctly signed and
attributed to a user who never touched it. That is not a hypothetical class of
bug; it is what link unfurling does by design.

The rest covers the token lifecycle: forged (403), someone else's (403), reused
(409), expired (410).
"""

from __future__ import annotations

import asyncio
import datetime

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base, utcnow
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.portfolio.const import AssetType
from kactus_common.portfolio.model import Portfolio, PortfolioItem, SupportedAsset
from kactus_common.project.service import ProjectService
from kactus_common.user import auth as auth_mod
from kactus_common.user.context import set_current_project_id
from kactus_common.user.model import User
from kactus_fin.action.const import ActionType
from kactus_fin.action.model import ActionToken
from kactus_fin.action.service import ActionTokenService
from sqlalchemy import select

TEST_DB_URL = "sqlite+aiosqlite://"
TEST_KEY = Fernet.generate_key().decode()
TEST_SECRET = "test-action-secret"


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
async def app(db, tmp_path):
    from kactus_common.config import clear_settings, register_settings
    from kactus_fin.app import create_app
    from kactus_fin.config import Settings

    register_settings(
        Settings(
            enable_portfolio_scheduler=False,
            db_path=str(tmp_path / "t.duckdb"),
            encryption_key=TEST_KEY,
            action_token_secret=TEST_SECRET,
            public_base_url="https://kactus.test",
        )
    )
    session_mod._db = db
    auth_mod._auth = None

    _app = create_app()
    yield _app

    session_mod._db = None
    auth_mod._auth = None
    clear_settings()


@pytest.fixture(autouse=True)
def _reset_project_ctx():
    """Keep the project ContextVar from leaking between tests."""
    set_current_project_id(None)
    yield
    set_current_project_id(None)


async def _make_user(db, email: str, username: str) -> User:
    async with db.get_session() as session:
        user = User.init(
            email=email,
            username=username,
            password_hash="Test123!",
            name=username,
            status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        # A non-admin user gets a personal project; the action API is project-gated.
        project = await ProjectService.ensure_personal_project(session, user=user)
        user._project_id = project.id
        return user


@pytest_asyncio.fixture
async def owner(db) -> User:
    return await _make_user(db, "owner@kactus.io", "owner")


@pytest_asyncio.fixture
async def stranger(db) -> User:
    return await _make_user(db, "stranger@kactus.io", "stranger")


def _client_for(app, user: User) -> AsyncClient:
    """A client authenticated as ``user`` by stubbing session resolution."""

    class _Auth:
        async def get_current_user(self, request):
            request.state.user = user
            # Mirror real auth: select the user's personal project so the
            # project-scoped SELECT filter and @permission checks apply.
            project_id = getattr(user, "_project_id", None)
            request.state.project_id = project_id
            set_current_project_id(project_id)
            return user

    auth_mod._auth = _Auth()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def client(app, owner):
    async with _client_for(app, owner) as c:
        yield c


@pytest_asyncio.fixture
async def portfolio(db, owner) -> Portfolio:
    """A portfolio plus one catalog entry the add-item action can reference."""
    # Create under the owner's project so the row is scoped like a real request.
    set_current_project_id(owner._project_id)
    try:
        async with db.get_session() as session:
            p = Portfolio.init(owner_id=owner.id, name="Danh mục chính")
            session.add(p)
            session.add(
                SupportedAsset.init(
                    asset_type=str(AssetType.STOCK), code="FPT", name="FPT Corp"
                )
            )
            await session.commit()
            await session.refresh(p)
            return p
    finally:
        set_current_project_id(None)


async def _issue(db, user: User, action: ActionType, params: dict) -> str:
    # Issue under the user's project so the token carries the same project_id a
    # real (project-scoped) request would stamp on it.
    set_current_project_id(getattr(user, "_project_id", None))
    try:
        async with db.get_session() as session:
            _, token = await ActionTokenService.issue(
                session, user_id=user.id, action=action, params=params
            )
            return token
    finally:
        set_current_project_id(None)


# --------------------------------------------------------------------------- #
# ⚠️ The one that matters: GET is inert
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_never_consumes_or_executes(client, db, owner, portfolio):
    """Five previews must leave the token unused and the portfolio untouched."""
    token = await _issue(
        db,
        owner,
        ActionType.PORTFOLIO_ADD_ITEM,
        {"portfolio_id": portfolio.id, "asset_type": "STOCK", "code": "FPT"},
    )

    for _ in range(5):
        resp = await client.get(f"/api/actions/{token}")
        assert resp.status_code == 200
        assert "Confirm" in resp.text

    async with db.get_session() as session:
        rows = (await session.execute(select(ActionToken))).scalars().all()
        assert [r.consumed_at for r in rows] == [None]
        assert await PortfolioItem.all(session, portfolio_id=portfolio.id) == []


@pytest.mark.asyncio
async def test_confirmation_page_shows_what_will_happen(client, db, owner, portfolio):
    """The page has to be readable, or 'confirm' means nothing."""
    token = await _issue(
        db,
        owner,
        ActionType.PORTFOLIO_ADD_ITEM,
        {"portfolio_id": portfolio.id, "asset_type": "STOCK", "code": "FPT"},
    )
    body = (await client.get(f"/api/actions/{token}")).text

    assert "Add an asset to a portfolio" in body
    assert "FPT" in body
    assert f"action='/api/actions/{token}'" in body
    assert "method='post'" in body


# --------------------------------------------------------------------------- #
# POST executes — exactly once
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_post_executes_the_action(client, db, owner, portfolio):
    token = await _issue(
        db,
        owner,
        ActionType.PORTFOLIO_ADD_ITEM,
        {"portfolio_id": portfolio.id, "asset_type": "STOCK", "code": "fpt"},
    )
    resp = await client.post(f"/api/actions/{token}")

    assert resp.status_code == 200
    assert "Added STOCK:FPT" in resp.text

    async with db.get_session() as session:
        items = await PortfolioItem.all(session, portfolio_id=portfolio.id)
        # The handler upper-cases, so the lower-case code in the params still
        # matches the catalog.
        assert [(i.asset_type, i.code) for i in items] == [("STOCK", "FPT")]
        row = (await session.execute(select(ActionToken))).scalars().one()
        assert row.consumed_at is not None


@pytest.mark.asyncio
async def test_reuse_is_409(client, db, owner, portfolio):
    token = await _issue(
        db,
        owner,
        ActionType.PORTFOLIO_ADD_ITEM,
        {"portfolio_id": portfolio.id, "asset_type": "STOCK", "code": "FPT"},
    )
    assert (await client.post(f"/api/actions/{token}")).status_code == 200

    second = await client.post(f"/api/actions/{token}")
    assert second.status_code == 409
    assert second.json()["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_concurrent_posts_execute_once(client, db, owner, portfolio):
    """Two clicks in the same instant: the conditional UPDATE picks a winner.

    Without it both requests read ``consumed_at IS NULL``, both pass validation
    and both run the handler — the classic double-submit that a check-then-act
    consume cannot prevent.
    """
    token = await _issue(
        db,
        owner,
        ActionType.PORTFOLIO_ADD_ITEM,
        {"portfolio_id": portfolio.id, "asset_type": "STOCK", "code": "FPT"},
    )

    results = await asyncio.gather(
        client.post(f"/api/actions/{token}"),
        client.post(f"/api/actions/{token}"),
    )
    assert sorted(r.status_code for r in results) == [200, 409]

    async with db.get_session() as session:
        items = await PortfolioItem.all(session, portfolio_id=portfolio.id)
        assert len(items) == 1


# --------------------------------------------------------------------------- #
# Rejections
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_tampered_signature_is_403(client, db, owner, portfolio):
    token = await _issue(
        db,
        owner,
        ActionType.PORTFOLIO_ADD_ITEM,
        {"portfolio_id": portfolio.id, "asset_type": "STOCK", "code": "FPT"},
    )
    forged = token[:-1] + ("A" if token[-1] != "A" else "B")

    resp = await client.post(f"/api/actions/{forged}")
    assert resp.status_code == 403
    assert resp.json()["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_edited_payload_invalidates_the_signature(client, db, owner, portfolio):
    """The MAC covers the params, so rewriting the row breaks the token.

    An attacker with write access to one row cannot turn an approved
    "add FPT" into "add something else" — the link stops verifying.
    """
    token = await _issue(
        db,
        owner,
        ActionType.PORTFOLIO_ADD_ITEM,
        {"portfolio_id": portfolio.id, "asset_type": "STOCK", "code": "FPT"},
    )
    async with db.get_session() as session:
        row = (await session.execute(select(ActionToken))).scalars().one()
        row.params = {**row.params, "code": "VNM"}
        await row.save(session)

    assert (await client.post(f"/api/actions/{token}")).status_code == 403


@pytest.mark.asyncio
async def test_another_users_token_is_403(app, db, owner, stranger, portfolio):
    token = await _issue(
        db,
        owner,
        ActionType.PORTFOLIO_ADD_ITEM,
        {"portfolio_id": portfolio.id, "asset_type": "STOCK", "code": "FPT"},
    )
    async with _client_for(app, stranger) as c:
        resp = await c.post(f"/api/actions/{token}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_expired_token_is_410(client, db, owner, portfolio):
    token = await _issue(
        db,
        owner,
        ActionType.PORTFOLIO_REFRESH,
        {"portfolio_id": portfolio.id},
    )
    async with db.get_session() as session:
        row = (await session.execute(select(ActionToken))).scalars().one()
        row.expires_at = utcnow() - datetime.timedelta(seconds=1)
        await row.save(session)

    resp = await client.post(f"/api/actions/{token}")
    assert resp.status_code == 410
    assert resp.json()["code"] == "GONE"

    # And the confirmation page says so too, rather than offering a dead button.
    assert (await client.get(f"/api/actions/{token}")).status_code == 410


@pytest.mark.asyncio
async def test_garbage_token_is_403_not_500(client):
    # The empty token is not in this list: ``/api/actions/`` redirects to the
    # issue endpoint rather than reaching the token route at all.
    for junk in ("abc", "abc.def", "1", "9999999999.AAAA"):
        resp = await client.post(f"/api/actions/{junk}")
        assert resp.status_code == 403, junk


@pytest.mark.asyncio
async def test_unset_secret_fails_closed(client, db, owner, portfolio, monkeypatch):
    """No signing secret ⇒ no action links, rather than links that all verify.

    ``compare_digest`` over two MACs of an empty key succeeds, so a deployment
    that forgot the variable would accept forged tokens while looking healthy.
    """
    from kactus_common import config as config_mod
    from kactus_common.exceptions import ConfigurationError

    token = await _issue(
        db, owner, ActionType.PORTFOLIO_REFRESH, {"portfolio_id": portfolio.id}
    )
    monkeypatch.setattr(config_mod.settings, "action_token_secret", "", raising=False)

    with pytest.raises(ConfigurationError):
        async with db.get_session() as session:
            await ActionTokenService.resolve(session, token, user_id=owner.id)


# --------------------------------------------------------------------------- #
# The producer side — what goes into NotificationEvent.url
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_url_for_uses_the_public_base_url(app, db, owner, portfolio):
    """The link is read on someone's phone, so it cannot say localhost."""
    token = await _issue(
        db, owner, ActionType.PORTFOLIO_REFRESH, {"portfolio_id": portfolio.id}
    )
    assert (
        ActionTokenService.url_for(token) == f"https://kactus.test/api/actions/{token}"
    )


@pytest.mark.asyncio
async def test_issue_endpoint_returns_a_working_link(client, portfolio):
    """Round trip through HTTP: mint a link, then use it."""
    resp = await client.post(
        "/api/actions",
        json={
            "action": "portfolio.add_item",
            "params": {
                "portfolio_id": str(portfolio.id),
                "asset_type": "STOCK",
                "code": "FPT",
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["url"] == f"https://kactus.test/api/actions/{data['token']}"

    assert (await client.post(f"/api/actions/{data['token']}")).status_code == 200


@pytest.mark.asyncio
async def test_issue_ignores_a_user_id_in_the_body(client, db, owner, stranger):
    """The subject is the session user, never something the caller names.

    A caller who could pick the subject could mint a link that runs against
    another account, which would undo the ownership check the rest of this
    feature is built on.
    """
    resp = await client.post(
        "/api/actions",
        json={
            "action": "notification.mute_channel",
            "params": {"channel_id": "1"},
            "user_id": str(stranger.id),
        },
    )
    assert resp.status_code == 200

    async with db.get_session() as session:
        row = (await session.execute(select(ActionToken))).scalars().one()
        assert row.user_id == owner.id


@pytest.mark.asyncio
async def test_issue_rejects_an_unknown_action(client):
    resp = await client.post(
        "/api/actions", json={"action": "portfolio.teleport", "params": {}}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_issue_rejects_an_action_with_no_handler(app, db, owner):
    """Better to fail at issue than to send a link that 500s when clicked."""
    from kactus_common.exceptions import InvalidArgumentError
    from kactus_fin.action import service as service_mod

    async with db.get_session() as session:
        with pytest.raises(InvalidArgumentError):
            await service_mod.ActionTokenService.issue(
                session, user_id=owner.id, action="portfolio.teleport", params={}
            )
