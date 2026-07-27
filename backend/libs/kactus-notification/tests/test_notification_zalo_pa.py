"""Tests for the Zalo PA channel.

No network / no real Zalo: the ``curl_cffi`` client and the ``zlapi`` bot are
faked. Covers config masking, the plain-text template, the blocking send +
deterministic-error mapping, recipient mapping, the in-process session store,
and the QR-login steps (generate / scan / complete).
"""

from __future__ import annotations

import types

import pytest
from kactus_common.config import CommonSettings, clear_settings, register_settings
from kactus_common.exceptions import ExternalServiceError, ValidationError
from kactus_notification import zalo_pa
from kactus_notification.channel import RenderedMessage, ZaloPAChannel
from kactus_notification.config import NotificationSettings
from kactus_notification.const import NotificationChannelType
from kactus_notification.registry import build_channel, get_template
from kactus_notification.schema import (
    NotificationEvent,
    ZaloPAChannelConfig,
    ZaloRecipientTarget,
    mask_config,
)
from zlapi.models import ZaloAPIException

_SESSION_FIELDS = {
    "cookies": {"zpdid": "dev1"},
    "imei": "dev1",
    "zpw_sek": "sek",
    "zpsid": "sid",
    "secret_key": "SK",
    "user_agent": "ua",
    "zalo_user_id": "u1",
    "account_name": "Me",
}

CONFIG = {
    **_SESSION_FIELDS,
    "recipients": [{"thread_id": "42", "thread_type": 0, "name": "Bob"}],
}

MULTI_CONFIG = {
    **_SESSION_FIELDS,
    "recipients": [
        {"thread_id": "42", "thread_type": 0, "name": "Bob"},
        {"thread_id": "g7", "thread_type": 1, "name": "Team"},
    ],
}

# Pre-multi-recipient shape still present in existing DB rows.
LEGACY_CONFIG = {
    **_SESSION_FIELDS,
    "thread_id": "42",
    "thread_type": 0,
    "recipient_name": "Bob",
}


class _Settings(CommonSettings, NotificationSettings):
    """Composite settings, mirroring how kactus-fin merges the two branches.

    ``app_env`` comes from the kactus-common branch, the ``zalo_pa_*`` knobs from
    the kactus-notification one. A bare ``CommonSettings`` would silently drop
    the latter (``extra="ignore"``) instead of rejecting them.
    """


@pytest.fixture(autouse=True)
def _settings():
    register_settings(
        _Settings(app_env="dev", zalo_pa_session_ttl_secs=300, zalo_pa_max_sessions=50)
    )
    yield
    zalo_pa.reset_session_store()
    clear_settings()


# --------------------------------------------------------------------------- #
# Config / masking / template
# --------------------------------------------------------------------------- #
def test_config_validates_and_masks():
    cfg = ZaloPAChannelConfig.model_validate(CONFIG)
    assert [r.thread_id for r in cfg.recipients] == ["42"]
    masked = mask_config(NotificationChannelType.ZALO_PA, CONFIG)
    for secret in ("cookies", "imei", "zpw_sek", "zpsid", "secret_key"):
        assert masked[secret] == "***"
    # Non-secret display/recipient fields stay visible.
    assert masked["recipients"][0]["thread_id"] == "42"
    assert masked["account_name"] == "Me"


def test_legacy_config_lifts_scalar_recipient():
    """Old single-target rows keep working: scalar keys fold into recipients."""
    cfg = ZaloPAChannelConfig.model_validate(LEGACY_CONFIG)
    assert len(cfg.recipients) == 1
    target = cfg.recipients[0]
    assert (target.thread_id, target.thread_type, target.name) == ("42", 0, "Bob")
    # New-shape dump carries no legacy scalar keys.
    dumped = cfg.model_dump()
    assert "thread_id" not in dumped and "recipient_name" not in dumped


def test_template_is_plaintext():
    tpl = get_template(NotificationChannelType.ZALO_PA)
    rendered = tpl.render(
        NotificationEvent(
            title="Giá vàng",
            body="SJC tăng",
            level="warning",
            fields=[("SJC", "1tr")],
            url="http://x",
        )
    )
    assert rendered.payload is None  # plain text, no rich payload
    assert "Giá vàng" in rendered.text
    assert "SJC: 1tr" in rendered.text
    assert "<b>" not in rendered.text  # no markup


# --------------------------------------------------------------------------- #
# Channel send (multi-recipient)
# --------------------------------------------------------------------------- #
def test_channel_send_delivers_to_all_recipients(monkeypatch):
    calls: list[tuple[str, int]] = []
    sleeps: list[float] = []
    monkeypatch.setattr(zalo_pa, "build_sync_bot", lambda cfg: "BOT")
    monkeypatch.setattr(
        zalo_pa,
        "send_text_sync",
        lambda bot, text, thread_id, thread_type: calls.append(
            (thread_id, thread_type)
        ),
    )
    monkeypatch.setattr("time.sleep", lambda secs: sleeps.append(secs))

    ch = build_channel(NotificationChannelType.ZALO_PA, MULTI_CONFIG)
    assert isinstance(ch, ZaloPAChannel)
    with ch:
        ch.send(RenderedMessage(text="hello"))
    assert calls == [("42", 0), ("g7", 1)]
    # Anti-spam gap only *between* sends, not before the first.
    assert sleeps == [zalo_pa.SEND_DELAY_SECS]


def test_channel_send_partial_success_does_not_raise(monkeypatch):
    """Once any target got the message, never raise — a retry would double-send."""
    monkeypatch.setattr(zalo_pa, "build_sync_bot", lambda cfg: "BOT")
    monkeypatch.setattr("time.sleep", lambda secs: None)
    delivered: list[str] = []

    def _first_fails(bot, text, thread_id, thread_type):
        if thread_id == "42":
            raise ZaloAPIException("logged out")
        delivered.append(thread_id)

    monkeypatch.setattr(zalo_pa, "send_text_sync", _first_fails)

    ch = build_channel(NotificationChannelType.ZALO_PA, MULTI_CONFIG)
    with ch:
        ch.send(RenderedMessage(text="hi"))  # must not raise
    assert delivered == ["g7"]


def test_channel_send_expired_session_is_non_retryable(monkeypatch):
    monkeypatch.setattr(zalo_pa, "build_sync_bot", lambda cfg: "BOT")
    monkeypatch.setattr("time.sleep", lambda secs: None)

    def _boom(bot, text, thread_id, thread_type):
        raise ZaloAPIException("logged out")

    monkeypatch.setattr(zalo_pa, "send_text_sync", _boom)

    ch = build_channel(NotificationChannelType.ZALO_PA, MULTI_CONFIG)
    with ch:
        # All targets ZaloAPIException → ExternalServiceError (not retried).
        with pytest.raises(ExternalServiceError):
            ch.send(RenderedMessage(text="hi"))


def test_channel_send_all_transient_failures_stay_retryable(monkeypatch):
    """Zero deliveries + transport error → re-raise so the dispatcher retries."""
    monkeypatch.setattr(zalo_pa, "build_sync_bot", lambda cfg: "BOT")

    def _net_down(bot, text, thread_id, thread_type):
        raise ConnectionError("reset")

    monkeypatch.setattr(zalo_pa, "send_text_sync", _net_down)

    ch = build_channel(NotificationChannelType.ZALO_PA, CONFIG)
    with ch:
        with pytest.raises(ConnectionError):
            ch.send(RenderedMessage(text="hi"))


def test_channel_send_without_recipients_is_misconfig(monkeypatch):
    monkeypatch.setattr(zalo_pa, "build_sync_bot", lambda cfg: "BOT")
    ch = build_channel(
        NotificationChannelType.ZALO_PA, {**_SESSION_FIELDS, "recipients": []}
    )
    with ch:
        with pytest.raises(ExternalServiceError):
            ch.send(RenderedMessage(text="hi"))


# --------------------------------------------------------------------------- #
# Recipient mapping (ZlapiAsync.list_recipients)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_recipients_maps_friends_and_groups():
    friend = types.SimpleNamespace(userId="u9", displayName="Alice", avatar="a.png")
    # Aliased friend: name lives under zaloName, avatar under avt, id under id.
    aliased = {"id": "u10", "zaloName": "Chị Hai", "avt": "b.png"}
    groups = types.SimpleNamespace(gridVerMap={"g1": 3, "g2": 5})
    group_info = types.SimpleNamespace(
        gridInfoMap={
            "g1": {"name": "Team", "avt": "g.png"},
            # Fallback keys: groupName + fullAvt.
            "g2": {"groupName": "Crew", "fullAvt": "f.png"},
        }
    )
    bot = types.SimpleNamespace(
        user_id="me",
        fetchAllFriends=lambda: [friend, aliased],
        fetchAllGroups=lambda: groups,
        fetchGroupInfo=lambda gm: group_info,
    )
    client = zalo_pa.ZlapiAsync(bot)
    recipients = await client.list_recipients()
    by_id = {r.id: r for r in recipients}
    assert by_id["u9"].name == "Alice" and by_id["u9"].is_group is False
    assert by_id["u10"].name == "Chị Hai" and by_id["u10"].avatar == "b.png"
    assert by_id["g1"].name == "Team" and by_id["g1"].is_group is True
    assert by_id["g2"].name == "Crew" and by_id["g2"].avatar == "f.png"

    # Query filters by name (case-insensitive).
    only_team = await client.list_recipients("team")
    assert [r.id for r in only_team] == ["g1"]


# --------------------------------------------------------------------------- #
# Channel-level operations (stored config, no QR session)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_channel_recipients_uses_stored_credentials(monkeypatch):
    captured: dict = {}

    class _FakeZlapi:
        @classmethod
        async def create(cls, credentials):
            captured.update(credentials)
            return cls()

        async def list_recipients(self, query=""):
            return [zalo_pa.Recipient(id="u1", name="Alice")]

    monkeypatch.setattr(zalo_pa, "ZlapiAsync", _FakeZlapi)
    cfg = ZaloPAChannelConfig.model_validate(CONFIG)
    out = await zalo_pa.list_channel_recipients(cfg)
    assert [r.id for r in out] == ["u1"]
    assert captured == {
        "cookies": {"zpdid": "dev1"},
        "imei": "dev1",
        "user_agent": "ua",
    }


@pytest.mark.asyncio
async def test_list_channel_recipients_dead_session_is_external_error(monkeypatch):
    class _DeadZlapi:
        @classmethod
        async def create(cls, credentials):
            raise ZaloAPIException("session expired")

    monkeypatch.setattr(zalo_pa, "ZlapiAsync", _DeadZlapi)
    cfg = ZaloPAChannelConfig.model_validate(CONFIG)
    with pytest.raises(ExternalServiceError):
        await zalo_pa.list_channel_recipients(cfg)


@pytest.mark.asyncio
async def test_send_greeting_collects_per_target_results(monkeypatch):
    sent: list[tuple[str, str, int]] = []
    sleeps: list[float] = []

    class _FakeZlapi:
        @classmethod
        async def create(cls, credentials):
            return cls()

        async def send_text(self, text, thread_id, thread_type=0):
            if thread_id == "g7":
                raise ZaloAPIException("kicked from group")
            sent.append((text, thread_id, thread_type))

    async def _no_sleep(secs):
        sleeps.append(secs)

    monkeypatch.setattr(zalo_pa, "ZlapiAsync", _FakeZlapi)
    monkeypatch.setattr(zalo_pa.asyncio, "sleep", _no_sleep)

    cfg = ZaloPAChannelConfig.model_validate(MULTI_CONFIG)
    results = await zalo_pa.send_greeting_to_recipients(cfg, zalo_pa.TEST_GREETING)
    assert sent == [(zalo_pa.TEST_GREETING, "42", 0)]
    assert sleeps == [zalo_pa.SEND_DELAY_SECS]  # only between targets
    assert results[0]["ok"] is True and results[0]["thread_id"] == "42"
    assert results[1]["ok"] is False and "kicked" in results[1]["error"]


@pytest.mark.asyncio
async def test_send_greeting_requires_recipients():
    cfg = ZaloPAChannelConfig.model_validate({**_SESSION_FIELDS, "recipients": []})
    with pytest.raises(ValidationError):
        await zalo_pa.send_greeting_to_recipients(cfg, "hi")


# --------------------------------------------------------------------------- #
# Session store + build_channel_config
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_session_store_save_load_delete():
    store = zalo_pa.get_session_store()
    assert isinstance(store, zalo_pa.InProcessZaloPASessionStore)  # default backend
    await store.save("s1", {"code": "C"}, 300)
    assert await store.load("s1") == {"code": "C"}
    assert await store.count() == 1
    await store.delete("s1")
    assert await store.load("s1") is None
    assert await store.count() == 0


@pytest.mark.asyncio
async def test_session_store_expires_after_ttl():
    """A session past its TTL reads as absent — the flow restarts at step 1."""
    store = zalo_pa.get_session_store()
    await store.save("s0", {"code": "C"}, 0)  # already expired
    assert await store.load("s0") is None
    assert await store.count() == 0


@pytest.mark.asyncio
async def test_build_channel_config_requires_completed_session():
    with pytest.raises(ValidationError):
        await zalo_pa.build_channel_config(
            "missing", recipients=[ZaloRecipientTarget(thread_id="1")]
        )


@pytest.mark.asyncio
async def test_build_channel_config_from_completed_session():
    await zalo_pa.get_session_store().save(
        "s2",
        {
            "complete": True,
            "credentials": {
                "cookies": {"zpdid": "d"},
                "imei": "d",
                "zpw_sek": "z",
                "zpsid": "p",
                "secret_key": "k",
                "user_agent": "ua",
            },
            "zalo_user_id": "u1",
            "account_name": "Me",
        },
        300,
    )
    cfg = await zalo_pa.build_channel_config(
        "s2",
        recipients=[
            ZaloRecipientTarget(thread_id="42", thread_type=1, name="Team"),
            ZaloRecipientTarget(thread_id="u5", thread_type=0, name="Bob"),
        ],
    )
    assert [(r.thread_id, r.thread_type) for r in cfg.recipients] == [
        ("42", 1),
        ("u5", 0),
    ]
    assert cfg.zalo_user_id == "u1"
    assert cfg.secret_key == "k"


# --------------------------------------------------------------------------- #
# QR login steps (mocked curl_cffi client + ZlapiAsync)
# --------------------------------------------------------------------------- #
class _Cookie:
    def __init__(self, name, value):
        self.name, self.value = name, value


class _CookieJar:
    def __init__(self):
        self.jar: list[_Cookie] = []

    def set(self, name, value):
        self.jar.append(_Cookie(name, value))


class _Resp:
    def __init__(self, status_code=200, json_data=None, headers=None, content=b"x"):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = headers or {}
        self.content = content
        self.cookies = _CookieJar()

    def json(self):
        return self._json

    @property
    def text(self):
        return str(self._json)


class _FakeClient:
    def __init__(self, responses):
        self.cookies = _CookieJar()
        self._responses = list(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kw):
        return self._responses.pop(0)

    async def post(self, url, **kw):
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_generate_qr_stores_session(monkeypatch):
    client = _FakeClient(
        [_Resp(200, {}), _Resp(200, {"data": {"code": "CODE", "image": "IMG"}})]
    )
    monkeypatch.setattr(zalo_pa, "_make_client", lambda *a, **k: client)
    result = await zalo_pa.generate_qr("sid1")
    assert result == {"code": "CODE", "image_url": "IMG"}
    assert (await zalo_pa.get_session_store().load("sid1"))["code"] == "CODE"


@pytest.mark.asyncio
async def test_wait_for_scan_scanned_and_refreshed(monkeypatch):
    await zalo_pa.get_session_store().save("sid2", {"code": "C", "cookies": {}}, 300)

    scanned = _FakeClient(
        [_Resp(200, {"error_code": 0, "data": {"display_name": "Me", "avatar": "a"}})]
    )
    monkeypatch.setattr(zalo_pa, "_make_client", lambda *a, **k: scanned)
    result = await zalo_pa.wait_for_scan("sid2")
    assert result["status"] == "scanned"
    assert result["display_name"] == "Me"

    refreshed = _FakeClient(
        [
            _Resp(
                200,
                {"error_code": 0, "data": {"status": 4, "code": "NEW", "image": "I2"}},
            )
        ]
    )
    monkeypatch.setattr(zalo_pa, "_make_client", lambda *a, **k: refreshed)
    result = await zalo_pa.wait_for_scan("sid2")
    assert result["status"] == "refreshed"
    assert result["code"] == "NEW"
    assert (await zalo_pa.get_session_store().load("sid2"))["code"] == "NEW"


@pytest.mark.asyncio
async def test_complete_login_verifies_account(monkeypatch):
    await zalo_pa.get_session_store().save("sid3", {"code": "C", "cookies": {}}, 300)

    async def _fake_init(session_id):
        return {"zpdid": "dev1", "zpw_sek": "sek", "zpsid": "sid"}

    class _FakeZlapi:
        @classmethod
        async def create(cls, credentials):
            return cls()

        async def get_secret_key(self):
            return "SK"

        async def fetch_account_info(self):
            return {"profile": {"userId": "u1", "displayName": "Trader"}}

    monkeypatch.setattr(zalo_pa, "_init_chat_session", _fake_init)
    monkeypatch.setattr(zalo_pa, "ZlapiAsync", _FakeZlapi)

    result = await zalo_pa.complete_login("sid3")
    assert result == {"zalo_user_id": "u1", "account_name": "Trader"}
    state = await zalo_pa.get_session_store().load("sid3")
    assert state["complete"] is True
    assert state["credentials"]["secret_key"] == "SK"
