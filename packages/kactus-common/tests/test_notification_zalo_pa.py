"""Tests for the Zalo PA channel (kactus-common).

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
from kactus_common.notification import zalo_pa
from kactus_common.notification.channel import RenderedMessage, ZaloPAChannel
from kactus_common.notification.const import NotificationChannelType
from kactus_common.notification.registry import build_channel, get_template
from kactus_common.notification.schema import (
    NotificationEvent,
    ZaloPAChannelConfig,
    mask_config,
)
from zlapi.models import ZaloAPIException

CONFIG = {
    "cookies": {"zpdid": "dev1"},
    "imei": "dev1",
    "zpw_sek": "sek",
    "zpsid": "sid",
    "secret_key": "SK",
    "user_agent": "ua",
    "thread_id": "42",
    "thread_type": 0,
    "recipient_name": "Bob",
    "zalo_user_id": "u1",
    "account_name": "Me",
}


@pytest.fixture(autouse=True)
def _settings():
    register_settings(
        CommonSettings(
            app_env="dev", zalo_pa_session_ttl_secs=300, zalo_pa_max_sessions=50
        )
    )
    yield
    zalo_pa.session_store._sessions.clear()
    clear_settings()


# --------------------------------------------------------------------------- #
# Config / masking / template
# --------------------------------------------------------------------------- #
def test_config_validates_and_masks():
    cfg = ZaloPAChannelConfig.model_validate(CONFIG)
    assert cfg.thread_id == "42"
    masked = mask_config(NotificationChannelType.ZALO_PA, CONFIG)
    for secret in ("cookies", "imei", "zpw_sek", "zpsid", "secret_key"):
        assert masked[secret] == "***"
    # Non-secret display/recipient fields stay visible.
    assert masked["thread_id"] == "42"
    assert masked["account_name"] == "Me"


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
# Channel send
# --------------------------------------------------------------------------- #
def test_channel_send_uses_recipient(monkeypatch):
    recorded = {}
    monkeypatch.setattr(zalo_pa, "build_sync_bot", lambda cfg: "BOT")

    def _fake_send(bot, text, thread_id, thread_type):
        recorded.update(
            bot=bot, text=text, thread_id=thread_id, thread_type=thread_type
        )

    monkeypatch.setattr(zalo_pa, "send_text_sync", _fake_send)

    ch = build_channel(NotificationChannelType.ZALO_PA, CONFIG)
    assert isinstance(ch, ZaloPAChannel)
    with ch:
        ch.send(RenderedMessage(text="hello"))
    assert recorded == {
        "bot": "BOT",
        "text": "hello",
        "thread_id": "42",
        "thread_type": 0,
    }


def test_channel_send_expired_session_is_non_retryable(monkeypatch):
    monkeypatch.setattr(zalo_pa, "build_sync_bot", lambda cfg: "BOT")

    def _boom(bot, text, thread_id, thread_type):
        raise ZaloAPIException("logged out")

    monkeypatch.setattr(zalo_pa, "send_text_sync", _boom)

    ch = build_channel(NotificationChannelType.ZALO_PA, CONFIG)
    with ch:
        # ZaloAPIException → ExternalServiceError (deterministic, not retried).
        with pytest.raises(ExternalServiceError):
            ch.send(RenderedMessage(text="hi"))


# --------------------------------------------------------------------------- #
# Recipient mapping (ZlapiAsync.list_recipients)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_recipients_maps_friends_and_groups():
    friend = types.SimpleNamespace(userId="u9", displayName="Alice", avatar="a.png")
    groups = types.SimpleNamespace(gridVerMap={"g1": 3})
    group_info = types.SimpleNamespace(
        gridInfoMap={"g1": {"name": "Team", "avt": "g.png"}}
    )
    bot = types.SimpleNamespace(
        user_id="me",
        fetchAllFriends=lambda: [friend],
        fetchAllGroups=lambda: groups,
        fetchGroupInfo=lambda gm: group_info,
    )
    client = zalo_pa.ZlapiAsync(bot)
    recipients = await client.list_recipients()
    by_id = {r.id: r for r in recipients}
    assert by_id["u9"].name == "Alice" and by_id["u9"].is_group is False
    assert by_id["g1"].name == "Team" and by_id["g1"].is_group is True

    # Query filters by name (case-insensitive).
    only_team = await client.list_recipients("team")
    assert [r.id for r in only_team] == ["g1"]


# --------------------------------------------------------------------------- #
# In-process session store + build_channel_config
# --------------------------------------------------------------------------- #
def test_session_store_save_load_delete():
    store = zalo_pa.session_store
    store.save("s1", {"code": "C"}, 300)
    assert store.load("s1") == {"code": "C"}
    assert store.count() == 1
    store.delete("s1")
    assert store.load("s1") is None
    assert store.count() == 0


def test_build_channel_config_requires_completed_session():
    with pytest.raises(ValidationError):
        zalo_pa.build_channel_config(
            "missing", thread_id="1", thread_type=0, recipient_name=None
        )


def test_build_channel_config_from_completed_session():
    zalo_pa.session_store.save(
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
    cfg = zalo_pa.build_channel_config(
        "s2", thread_id="42", thread_type=1, recipient_name="Team"
    )
    assert cfg.thread_id == "42"
    assert cfg.thread_type == 1
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
    assert zalo_pa.session_store.load("sid1")["code"] == "CODE"


@pytest.mark.asyncio
async def test_wait_for_scan_scanned_and_refreshed(monkeypatch):
    zalo_pa.session_store.save("sid2", {"code": "C", "cookies": {}}, 300)

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
    assert zalo_pa.session_store.load("sid2")["code"] == "NEW"


@pytest.mark.asyncio
async def test_complete_login_verifies_account(monkeypatch):
    zalo_pa.session_store.save("sid3", {"code": "C", "cookies": {}}, 300)

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
    state = zalo_pa.session_store.load("sid3")
    assert state["complete"] is True
    assert state["credentials"]["secret_key"] == "SK"
