"""Zalo Personal Account (PA) transport — QR login + zlapi send/recipient calls.

⚠️ **Unofficial.** Zalo has no public personal-account API; this drives
``id.zalo.me`` with a browser-impersonating ``curl_cffi`` client and the PyPI
``zlapi`` library. It carries a real **account-suspension risk** and may break
whenever Zalo changes. A **residential proxy** (``KACTUS_ZALO_PA_PROXY_URL``) is
required outside dev — datacenter IPs/TLS are blocked by Zalo's anti-fraud.

Push-only: we never run zlapi's WebSocket listener/sync — Kactus only *sends*
reports, so this ports reorc's ``auth.py`` (5-step QR login) + the direct
friend/group fetch, and drops the inbound/history machinery entirely.

The in-progress login lives in a TTL store keyed by ``session_id`` (see
:mod:`.session_store`). A channel row is created only once a recipient is
picked; its :class:`ZaloPAChannelConfig` then holds the credentials, encrypted
at rest by the ``EncryptedJSON`` config column.
"""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse, urlunparse

from curl_cffi.requests import AsyncSession as CurlAsyncSession
from kactus_common.config import settings
from kactus_common.exceptions import ExternalServiceError, ValidationError
from kactus_common.text import normalize_search
from loguru import logger
from zlapi import ZaloAPI
from zlapi import _client as _zlapi_client
from zlapi.models import Message, ThreadType

from ...schema import Recipient
from .schema import ZaloPAChannelConfig, ZaloRecipientTarget
from .session_store import get_session_store

# --------------------------------------------------------------------------- #
# Constants (ported from reorc zalo_pa/consts.py)
# --------------------------------------------------------------------------- #

ZALO_ID_BASE = "https://id.zalo.me"
CONTINUE_URL = "https://chat.zalo.me/"
FORM_DATA_VERSION = "5.6.1"
QR_SCAN_TIMEOUT = 60  # seconds to wait for a scan long-poll
QR_CONFIRM_TIMEOUT = 60  # seconds to wait for a confirm long-poll
SEND_DELAY_SECS = 1.5  # pause between consecutive sends (Zalo anti-spam)
TEST_GREETING = "Hello, nice to meet you"
TEST_MESSAGE_TITLE = "Test message"  # send-history title for the ⚡ greeting

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)

ZALO_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://id.zalo.me",
    "referer": "https://id.zalo.me/account?continue=https%3A%2F%2Fchat.zalo.me%2F",
    "user-agent": _USER_AGENT,
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}


# --------------------------------------------------------------------------- #
# Neutralize zlapi's os.kill(SIGTERM) — it kills the whole process on cmd=3000.
# (We never listen, but importing + constructing can still trip it.)
# --------------------------------------------------------------------------- #
class _NoKillOSProxy:
    def __init__(self, real_os):
        self.__dict__["_real"] = real_os

    def __getattr__(self, name):
        return getattr(self._real, name)

    def kill(self, pid, sig):  # noqa: ARG002 — signature must match os.kill
        raise ConnectionAbortedError(
            f"zlapi attempted os.kill(pid={pid}, sig={sig}) — intercepted"
        )


if not isinstance(_zlapi_client.os, _NoKillOSProxy):
    _zlapi_client.os = _NoKillOSProxy(_zlapi_client.os)


# --------------------------------------------------------------------------- #
# curl_cffi client helpers (Chrome TLS impersonation + residential proxy).
# --------------------------------------------------------------------------- #
def _proxy_url() -> str | None:
    """Residential proxy for non-dev; ``None`` in dev (local IP is fine)."""
    if settings.is_dev():
        return None
    if not settings.zalo_pa_proxy_url:
        logger.error(
            "[zalo_pa] zalo_pa_proxy_url unset in non-dev — QR login will likely fail"
        )
        return None
    return settings.zalo_pa_proxy_url


def _sticky_proxy_url(proxy_url: str, sticky_session: str) -> str:
    """Pin all requests of one QR flow to the same residential IP (BrightData)."""
    parsed = urlparse(proxy_url)
    username = parsed.username or ""
    clean_id = sticky_session.replace("-", "")
    new_username = f"{username}-session-{clean_id}"
    password = parsed.password or ""
    netloc = f"{new_username}:{password}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


def _make_client(
    cookies: dict[str, str] | None = None,
    *,
    sticky_session: str | None = None,
    use_proxy: bool = False,
) -> CurlAsyncSession:
    proxy = _proxy_url() if use_proxy else None
    if proxy and sticky_session:
        proxy = _sticky_proxy_url(proxy, sticky_session)
    client = CurlAsyncSession(
        headers=ZALO_HEADERS,
        impersonate="chrome",
        allow_redirects=True,
        timeout=10.0,
        proxy=proxy,
        verify=True,
    )
    if cookies:
        for name, value in cookies.items():
            client.cookies.set(name, value)
    return client


def _safe_cookies(client: CurlAsyncSession) -> dict[str, str]:
    return {c.name: c.value for c in client.cookies.jar}


def _merge_cookies(acc: dict[str, str], resp) -> dict[str, str]:
    for cookie in resp.cookies.jar:
        if cookie.value:
            acc[cookie.name] = cookie.value
    return acc


# --------------------------------------------------------------------------- #
# QR login — 5 steps (ported from reorc auth.py; DB replaced by session_store).
# --------------------------------------------------------------------------- #
async def generate_qr(session_id: str) -> dict:
    """Step 1 — visit login page, generate a QR. Returns ``{code, image_url}``."""
    if await get_session_store().count() >= settings.zalo_pa_max_sessions:
        raise ValidationError(
            f"Too many concurrent Zalo QR logins ({settings.zalo_pa_max_sessions}); "
            "wait and retry."
        )
    async with _make_client(sticky_session=session_id, use_proxy=True) as client:
        resp = await client.get(
            f"{ZALO_ID_BASE}/account", params={"continue": CONTINUE_URL}
        )
        cookies = _safe_cookies(client)
        _merge_cookies(cookies, resp)
        resp = await client.post(
            f"{ZALO_ID_BASE}/account/authen/qr/generate",
            data={"continue": CONTINUE_URL, "v": FORM_DATA_VERSION},
        )
        _merge_cookies(cookies, resp)

    if resp.status_code != 200 or not resp.content:
        raise ExternalServiceError(f"Zalo QR generate failed: HTTP {resp.status_code}")
    qr = (resp.json() or {}).get("data", {})
    code, image_url = qr.get("code"), qr.get("image")
    if not code or not image_url:
        raise ExternalServiceError(f"Zalo QR generate failed: {resp.json()}")

    await get_session_store().save(
        session_id,
        {"code": code, "cookies": cookies, "display_name": None, "avatar": None},
        settings.zalo_pa_session_ttl_secs,
    )
    logger.info("[zalo_pa] QR generated for session {sid}", sid=session_id)
    return {"code": code, "image_url": image_url}


async def _require_session(session_id: str) -> dict:
    state = await get_session_store().load(session_id)
    if not state:
        raise ValidationError("No active Zalo QR session — generate a QR first")
    return state


async def wait_for_scan(session_id: str) -> dict:
    """Step 2 — long-poll until the QR is scanned (or ``refreshed``/``expired``)."""
    state = await _require_session(session_id)
    cookies = state["cookies"]
    async with _make_client(
        cookies, sticky_session=session_id, use_proxy=True
    ) as client:
        try:
            resp = await client.post(
                f"{ZALO_ID_BASE}/account/authen/qr/waiting-scan",
                data={
                    "code": state["code"],
                    "continue": CONTINUE_URL,
                    "v": FORM_DATA_VERSION,
                },
                timeout=QR_SCAN_TIMEOUT + 5,
            )
            data = resp.json()
            _merge_cookies(cookies, resp)
        except Exception as exc:  # noqa: BLE001 — curl_cffi timeout = still waiting
            if "timeout" in str(exc).lower():
                return {"status": "expired"}
            raise

    if data.get("error_code") != 0:
        return {"status": "expired"}
    scan = data.get("data") or {}
    # status=4 + a new code = Zalo rotated the QR (anti-fraud); not a real scan.
    if scan.get("status") == 4 and scan.get("code"):
        state["code"] = scan["code"]
        state["cookies"] = cookies
        await get_session_store().touch(
            session_id, state, settings.zalo_pa_session_ttl_secs
        )
        return {
            "status": "refreshed",
            "code": scan["code"],
            "image_url": scan.get("image", ""),
        }
    state["display_name"] = scan.get("display_name")
    state["avatar"] = scan.get("avatar")
    state["cookies"] = cookies
    await get_session_store().touch(
        session_id, state, settings.zalo_pa_session_ttl_secs
    )
    return {
        "status": "scanned",
        "display_name": state["display_name"],
        "avatar": state["avatar"],
    }


async def wait_for_confirm(session_id: str) -> dict:
    """Step 3 — long-poll until the user confirms on their phone."""
    state = await _require_session(session_id)
    cookies = state["cookies"]
    async with _make_client(
        cookies, sticky_session=session_id, use_proxy=True
    ) as client:
        try:
            resp = await client.post(
                f"{ZALO_ID_BASE}/account/authen/qr/waiting-confirm",
                data={
                    "code": state["code"],
                    "gToken": "",
                    "gAction": "CONFIRM_QR",
                    "continue": CONTINUE_URL,
                    "v": FORM_DATA_VERSION,
                },
                timeout=QR_CONFIRM_TIMEOUT + 5,
            )
            data = resp.json()
            _merge_cookies(cookies, resp)
        except Exception as exc:  # noqa: BLE001
            if "timeout" in str(exc).lower():
                return {"status": "expired"}
            raise

    if data.get("error_code") != 0:
        return {"status": "rejected"}
    state["cookies"] = cookies
    await get_session_store().touch(
        session_id, state, settings.zalo_pa_session_ttl_secs
    )
    return {"status": "confirmed"}


async def _init_chat_session(session_id: str) -> dict:
    """Step 4a — follow the redirect chain to capture the ``zpw_sek`` cookie."""
    state = await _require_session(session_id)
    cookies = state["cookies"]
    async with _make_client(cookies) as client:
        resp = await client.get(
            f"{ZALO_ID_BASE}/account/checksession",
            params={"continue": CONTINUE_URL},
            allow_redirects=False,
            timeout=10.0,
        )
        _merge_cookies(cookies, resp)
        redirect_url = resp.headers.get("location", "")
        redirect_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "referer": "https://id.zalo.me/",
            "user-agent": _USER_AGENT,
        }
        all_cookies = {**cookies, **_safe_cookies(client)}
        for _ in range(5):
            if not redirect_url:
                break
            resp = await client.get(
                redirect_url,
                allow_redirects=False,
                timeout=10.0,
                headers=redirect_headers,
            )
            _merge_cookies(cookies, resp)
            all_cookies = {**cookies, **_safe_cookies(client)}
            if all_cookies.get("zpw_sek") not in (None, "EXPIRED"):
                break
            redirect_url = resp.headers.get("location", "")

    state["cookies"] = all_cookies
    await get_session_store().touch(
        session_id, state, settings.zalo_pa_session_ttl_secs
    )
    return all_cookies


async def complete_login(session_id: str) -> dict:
    """Step 4/5 — assemble credentials, verify the account, hold it in the store.

    Returns ``{zalo_user_id, account_name}``. The full credentials + recipient
    are turned into a :class:`ZaloPAChannelConfig` later, when a channel is
    created (:func:`build_channel_config`).
    """
    all_cookies = await _init_chat_session(session_id)
    imei = all_cookies.get("zpdid", "")
    if not imei:
        await get_session_store().delete(session_id)
        raise ExternalServiceError(
            "Zalo login failed: missing device id (zpdid) — re-scan the QR"
        )

    credentials = {
        "cookies": all_cookies,
        "imei": imei,
        "zpw_sek": all_cookies.get("zpw_sek", ""),
        "zpsid": all_cookies.get("zpsid", ""),
        "user_agent": _USER_AGENT,
    }
    try:
        client = await ZlapiAsync.create(credentials)
        credentials["secret_key"] = await client.get_secret_key()
        profile = (await client.fetch_account_info()).get("profile", {})
    except Exception as exc:  # noqa: BLE001
        await get_session_store().delete(session_id)
        raise ExternalServiceError(
            f"Zalo login failed: could not verify account ({exc}) — re-scan the QR"
        ) from exc

    zalo_user_id = str(profile.get("userId", ""))
    if not zalo_user_id:
        await get_session_store().delete(session_id)
        raise ExternalServiceError("Zalo login failed: no user id in account info")
    account_name = (
        profile.get("displayName")
        or profile.get("zaloName")
        or (await _require_session(session_id)).get("display_name")
        or "Zalo PA"
    )

    state = await _require_session(session_id)
    state.update(
        credentials=credentials,
        zalo_user_id=zalo_user_id,
        account_name=account_name,
        complete=True,
    )
    await get_session_store().touch(
        session_id, state, settings.zalo_pa_session_ttl_secs
    )
    logger.info(
        "[zalo_pa] login complete session={sid} user={uid}",
        sid=session_id,
        uid=zalo_user_id,
    )
    return {"zalo_user_id": zalo_user_id, "account_name": account_name}


async def _completed_session(session_id: str) -> dict:
    state = await _require_session(session_id)
    if not state.get("complete"):
        raise ValidationError("Zalo login not complete — finish the QR flow first")
    return state


async def list_session_recipients(session_id: str, query: str = "") -> list[Recipient]:
    """Friends + groups of a *completed* login session (the report-target picker)."""
    state = await _completed_session(session_id)
    client = await ZlapiAsync.create(state["credentials"])
    return await client.list_recipients(query)


async def build_channel_config(
    session_id: str,
    *,
    recipients: list[ZaloRecipientTarget],
) -> ZaloPAChannelConfig:
    """Assemble a :class:`ZaloPAChannelConfig` from a completed login session."""
    state = await _completed_session(session_id)
    creds = state["credentials"]
    return ZaloPAChannelConfig(
        cookies=creds["cookies"],
        imei=creds["imei"],
        zpw_sek=creds.get("zpw_sek", ""),
        zpsid=creds.get("zpsid", ""),
        secret_key=creds.get("secret_key", ""),
        user_agent=creds["user_agent"],
        recipients=recipients,
        zalo_user_id=state.get("zalo_user_id"),
        account_name=state.get("account_name"),
    )


async def session_credentials(session_id: str) -> dict:
    """Raw credential fields of a completed session (for channel re-auth)."""
    return dict((await _completed_session(session_id))["credentials"])


# --------------------------------------------------------------------------- #
# Sync helpers — used by ZaloPAChannel, whose send() already runs in a thread
# (dispatcher wraps _send_blocking in asyncio.to_thread), so no bridging needed.
# --------------------------------------------------------------------------- #
def build_sync_bot(config: ZaloPAChannelConfig) -> ZaloAPI:
    """Construct a blocking ``ZaloAPI`` straight from a channel's config."""
    return ZaloAPI("</>", "</>", imei=config.imei, cookies=config.cookies or {})


def send_text_sync(bot: ZaloAPI, text: str, thread_id: str, thread_type: int) -> None:
    """Blocking text send (0 = user, 1 = group)."""
    tt = ThreadType.GROUP if thread_type == 1 else ThreadType.USER
    bot.send(Message(text=text), thread_id=str(thread_id), thread_type=tt)


def _first(obj, *keys: str, default: object = "") -> object:
    """First truthy value under any of ``keys`` — attr or mapping access.

    zlapi returns Munch-like objects (attr *and* key access) but tests fake them
    with plain objects/dicts, so read both ways.
    """
    for key in keys:
        value = obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
        if value:
            return value
    return default


# --------------------------------------------------------------------------- #
# Async wrapper around sync zlapi.ZaloAPI — every call via asyncio.to_thread.
# --------------------------------------------------------------------------- #
class ZlapiAsync:
    """Minimal async wrapper — account probe, recipient fetch, text send."""

    def __init__(self, bot: ZaloAPI) -> None:
        self._bot = bot
        self.user_id = str(bot.user_id)

    @classmethod
    async def create(cls, credentials: dict) -> "ZlapiAsync":
        cookies = credentials.get("cookies", {})
        imei = credentials.get("imei") or cookies.get("zpdid", "")
        if not imei:
            raise ExternalServiceError("Missing Zalo device id (zpdid/imei)")
        bot = await asyncio.to_thread(ZaloAPI, "</>", "</>", imei=imei, cookies=cookies)
        return cls(bot)

    async def fetch_account_info(self) -> dict:
        return await asyncio.to_thread(self._bot.fetchAccountInfo)

    async def get_secret_key(self) -> str:
        return await asyncio.to_thread(self._bot.getSecretKey)

    async def fetch_all_friends(self) -> list:
        return await asyncio.to_thread(self._bot.fetchAllFriends)

    async def fetch_all_groups(self):
        return await asyncio.to_thread(self._bot.fetchAllGroups)

    async def fetch_group_info(self, grid_ver_map: dict):
        return await asyncio.to_thread(self._bot.fetchGroupInfo, grid_ver_map)

    async def send_text(self, text: str, thread_id: str, thread_type: int = 0) -> None:
        tt = ThreadType.GROUP if thread_type == 1 else ThreadType.USER
        await asyncio.to_thread(
            self._bot.send, Message(text=text), thread_id=str(thread_id), thread_type=tt
        )

    async def list_recipients(self, query: str = "") -> list[Recipient]:
        """Direct friends + groups → pickable recipients (no history/conversation).

        zlapi objects are Munch-like and the key that actually carries a value
        varies per account (an aliased friend has their name under ``zaloName``/
        ``dName``, not ``displayName``), so every field reads through a fallback
        chain rather than a single key.
        """
        recipients: list[Recipient] = []

        friends = await self.fetch_all_friends() or []
        for friend in friends:
            recipients.append(
                Recipient(
                    id=str(_first(friend, "userId", "id")),
                    name=str(
                        _first(
                            friend,
                            "displayName",
                            "zaloName",
                            "dName",
                            "username",
                            "name",
                        )
                    ),
                    avatar=_first(friend, "avatar", "avt", default=None),
                    is_group=False,
                )
            )

        try:
            groups_result = await self.fetch_all_groups()
            grid_ver_map = getattr(groups_result, "gridVerMap", {}) or {}
            details: dict = {}
            if grid_ver_map:
                info_result = await self.fetch_group_info(grid_ver_map)
                details = getattr(info_result, "gridInfoMap", {}) or {}
            for group_id in grid_ver_map:
                info = details.get(str(group_id), {}) or {}
                recipients.append(
                    Recipient(
                        id=str(group_id),
                        name=str(_first(info, "name", "groupName", "dName"))
                        or f"Group {str(group_id)[:8]}",
                        avatar=_first(info, "avt", "fullAvt", default=None),
                        is_group=True,
                    )
                )
        except Exception as exc:  # noqa: BLE001 — groups are best-effort
            logger.warning("[zalo_pa] could not list groups: {exc}", exc=exc)

        if query:
            q = normalize_search(query)
            recipients = [r for r in recipients if q in normalize_search(r.name)]
        return recipients


# --------------------------------------------------------------------------- #
# Channel-level operations — driven by a stored (already-decrypted)
# ZaloPAChannelConfig, no QR session involved. These back the conversations
# edit picker and the ⚡ test-message endpoint.
# --------------------------------------------------------------------------- #
def _channel_credentials(config: ZaloPAChannelConfig) -> dict:
    return {
        "cookies": config.cookies,
        "imei": config.imei,
        "user_agent": config.user_agent,
    }


async def list_channel_recipients(
    config: ZaloPAChannelConfig, query: str = ""
) -> list[Recipient]:
    """Friends + groups reachable with a channel's stored session (no re-scan).

    A dead/expired stored session surfaces as ``ExternalServiceError`` so the
    caller can offer a reconnect instead of a 500.
    """
    try:
        client = await ZlapiAsync.create(_channel_credentials(config))
        return await client.list_recipients(query)
    except ExternalServiceError:
        raise
    except Exception as exc:  # noqa: BLE001 — zlapi raises library-specific errors
        raise ExternalServiceError(
            f"Zalo recipients fetch failed (session may be expired — re-scan QR): {exc}"
        ) from exc


async def send_greeting_to_recipients(
    config: ZaloPAChannelConfig, text: str
) -> list[dict]:
    """Send ``text`` to every saved conversation; per-target results, no abort.

    Sequential sends with ``SEND_DELAY_SECS`` between them (anti-spam); one
    failed target does not stop the rest. Only a session that cannot even be
    hydrated raises — per-target failures come back as ``ok=False`` rows.
    """
    if not config.recipients:
        raise ValidationError("Channel has no saved conversations")
    try:
        client = await ZlapiAsync.create(_channel_credentials(config))
    except ExternalServiceError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ExternalServiceError(
            f"Zalo session invalid (re-scan the QR): {exc}"
        ) from exc

    results: list[dict] = []
    for index, target in enumerate(config.recipients):
        if index:
            await asyncio.sleep(SEND_DELAY_SECS)
        try:
            await client.send_text(text, target.thread_id, target.thread_type)
            results.append(
                {
                    "thread_id": target.thread_id,
                    "thread_type": target.thread_type,
                    "name": target.name,
                    "ok": True,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 — collect, don't abort the batch
            logger.warning(
                "[zalo_pa] test send to {tid} failed: {exc}",
                tid=target.thread_id,
                exc=exc,
            )
            results.append(
                {
                    "thread_id": target.thread_id,
                    "thread_type": target.thread_type,
                    "name": target.name,
                    "ok": False,
                    "error": str(exc),
                }
            )
    return results
