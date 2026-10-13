# Notification Feature — Multi-Channel Push (Telegram / Slack / Zalo PA)

> **Trạng thái**: ✅ **Implemented** (backend + frontend; 337 backend tests pass, frontend `tsc -b` + `vite build` xanh). Chưa live-smoke với Telegram/Zalo thật (cần token + quét QR + proxy). Xem **§14 As-built** cho các điểm khác blueprint.
> **Liên quan**: [01-tech-stack.md](01-tech-stack.md) · [03-feature-status.md](03-feature-status.md) · [04-portfolio-feature.md](04-portfolio-feature.md) · Zalo PA reference (reorc): `/Users/recurve/project/global/sbh/reorc-crm-server-base/app_crm/integrations/zalo_pa`

---

## 1. Tổng quan

Feature **`notification`**: user tạo các **kênh gửi** (notification channel) để nhận báo cáo/cảnh báo. Một kênh là một "notification connection" **dùng chung một model** cho mọi nền tảng — Telegram, Slack, Zalo Personal Account (PA) — phân biệt bởi `channel_type` + một `config` blob được ép schema theo từng loại. Mọi lần gửi được **ghi log** (audit "lịch sử gửi") và có **retry/backoff đồng bộ** cho lỗi mạng.

- **Push-only**: hệ thống chỉ **đẩy** thông báo tới user; không có chiều chat ngược (không webhook/inbound listener).
- **User-owned**: kênh thuộc về user tạo ra (ownership kiểm ở service, không qua Casbin `@permission`).
- **Event-driven auto-fire**: **defer** (TODO) — hạ tầng sẵn, chỉ cần thêm 1 handler bắt `data_refreshed`/price-alert → `Notifier.send_event(..., trigger=EVENT)`. `trigger=EVENT` đã được luồn sẵn qua log.

---

## 2. Quyết định đã chốt

| Vấn đề | Quyết định |
|--------|-----------|
| **1 model cho mọi nền tảng** | Dùng chung **`NotificationChannel`** (`channel_type` + `config: dict`). Mỗi loại có 1 Pydantic schema (`TelegramChannelConfig`, `SlackChannelConfig`, `ZaloPAChannelConfig`) ép `config`. **Không** có bảng riêng cho Zalo. |
| **Retry** | **Synchronous bounded** — retry ngay trong request, chỉ lỗi transport, mặc định 3 lần, backoff mũ (1s, 2s). |
| **Send-history** | Bảng `notification_logs` + API + UI (append-only, mirror `CrawlRun`). |
| **Zalo = Personal Account (PA)** | Qua thư viện PyPI **`zlapi`** (Zalo cá nhân không chính thức) — **không** OA. Pure-Python, in-process, bọc `asyncio.to_thread`. **Không** Node/zca-js sidecar, **không** Redis, **không** bảng conversation, **không** đồng bộ history, **không** WS listener. |
| **PA session ở đâu** | Nằm trong `NotificationChannel.config` (cookies/imei/zpw_sek/… + recipient). Mã hoá at-rest bởi cột `EncryptedJSON`; secret bị mask trong response. |
| **Nơi đặt code** | Notification là **shared infra** trong `kactus-common` (override quy tắc "no business logic in common", giống portfolio). HTTP layer ở `kactus-fin`. UI ở `kactus-bloom`. |

---

## 3. Kiến trúc

```
libs/kactus-notification (domain lib)        kactus-fin (HTTP)          kactus-bloom (UI)
  kactus_notification/
    const.py       enums                      notification/              modules/notification/
    schema.py      config schemas + event      api.py     CRUD/test/send    pages/  List, Detail
    model.py       NotificationChannel,        zalo_pa_api.py  QR + zalo    components/  Form, QR,
                   NotificationLog               app.py   register routers               Recipient,
    service.py     Channel + Log services                                                Log, SendTest
    channel.py     Telegram/Slack/ZaloPA      ─────────────▶  services/notificationService.ts
    template.py    per-type render                            hooks/useNotificationQuery.ts
    registry.py    dispatch tables                            types/notification.ts
    dispatcher.py  Notifier (retry + log)
    zalo_pa.py     QR login + zlapi wrapper
    config.py      NotificationSettings mixin
```

Dependency một chiều: `kactus-fin → kactus-notification → kactus-common`.
`Notifier` join channel đã lưu với registry channel/template — **bất kỳ package nào
depend `kactus-notification`** cũng gửi được.

**Tại sao là package riêng, không nằm trong `kactus-common`.** Hai lý do, cả hai
đều cụ thể:

1. `zlapi` là thư viện Zalo cá nhân **không chính thức, reverse-engineered** (tới
   mức phải có guard `_NoKillOSProxy` chặn `os.kill(SIGTERM)` của nó). Khai ở tầng
   đáy thì **mọi** package depend `kactus-common` đều kéo theo — kể cả
   `kactus-fin-gateway` vốn không bao giờ gửi notification. Giờ chỉ `kactus-fin` có.
2. `CLAUDE.md` quy định `kactus-common` là *infrastructure only, no business logic*.
   Channel registry, template rendering, retry policy, QR login 5 bước đều là
   domain logic.

`kactus-notification` và `kactus-data` là **anh em**, không package nào import
package kia — contract import-linter trong `pyproject.toml` chặn thật.

**Settings.** Chuỗi settings vốn tuyến tính (`CommonSettings → DataSettings →
Settings`) nên lib thứ hai không chen vào được. `NotificationSettings` là nhánh
song song mọc từ `BaseKactusSettings`, entry-point ghép bằng đa kế thừa:
`class Settings(DataSettings, NotificationSettings)`. Gateway không mix vào ⇒
settings của nó không hề có `zalo_pa_*`.

---

## 4. Generic seam (thêm 1 kênh = +1 config schema, +1 channel, +1 template)

Ba registry điều phối:

- `CHANNEL_CONFIG_SCHEMAS[type]` — schema ép `config` (schema.py).
- `SECRET_FIELDS[type]` — key bị mask trước khi rời API.
- `CHANNEL_REGISTRY[type]` / `TEMPLATE_REGISTRY[type]` — class channel / instance template (registry.py).

Thêm một loại kênh mới: thêm 1 entry vào mỗi registry + 1 `*ChannelConfig` + 1 `*Channel` + 1 `*EventTemplate`.

---

## 5. Channels

| Kênh | Transport | Config chính | Test | Template |
|------|-----------|--------------|------|----------|
| Telegram | `requests` → Bot API `sendMessage` | `bot_token`, `chat_id`, `parse_mode=HTML` | `getMe` | HTML |
| Slack | `requests` → Incoming Webhook | `webhook_url` | validate URL shape | Block Kit |
| Zalo PA | `zlapi` (sync, `to_thread`) → `send(Message, thread_id, ThreadType)` | session (cookies/imei/zpw_sek/…) + `thread_id`/`thread_type` | `fetchAccountInfo()` | plain text |

`retryable_exceptions` theo từng channel: base = `(requests.RequestException,)`; `ZaloPAChannel` thêm `ConnectionError`/`TimeoutError` và map `ZaloAPIException` (session hết hạn) → `ExternalServiceError` **không** retry.

---

## 6. Data model

**`notification_channels`** (`Base + ModelMixin + AuditMixin + LogicalDeleteMixin`): `owner_id`(idx), `name`, `channel_type`, `config` **`EncryptedJSON`**, `is_active`, `last_used_at`. Dùng chung cho mọi nền tảng — PA nhét cả session vào `config`.

**`notification_logs`** (`Base + ModelMixin`, append-only — gương `CrawlRun`): `channel_id`(idx), `owner_id`(idx), `channel_type`, `event_title`, `level`, `status`(idx), `trigger`, `attempts`, `error: Text`, `finished_at`; `started_at` = property alias `create_time`.

Migration: `20260710_000000_c3d4e5f6a7b8_add_notification_logs.py` (`down_revision="b2c3d4e5f6a7"`) tạo **chỉ** `notification_logs` (bảng `notification_channels` đã có từ trước, PA tái dùng).

---

## 7. Dispatcher + retry/backoff

`Notifier.send_event(session, channel, event, *, trigger=MANUAL)`:

1. `build_channel(type, config)` + `get_template(type).render(event)`.
2. Loop `1..notification_max_send_attempts`:
   - Gửi qua `asyncio.to_thread(_send_blocking, …)`.
   - Thành công → ghi `NotificationLog(status=SUCCESS, attempts=n)` rồi return.
   - `impl.retryable_exceptions` → log warning, `sleep(base_delay * 2**(n-1))`, thử lại.
   - `ExternalServiceError` (deterministic) → **break**, không retry.
3. Hết lượt → ghi `NotificationLog(status=FAILED, attempts=n, error=…)` rồi `raise ExternalServiceError`.

Settings: `notification_max_send_attempts=3`, `notification_retry_base_delay=1.0`. `Notifier.test` không retry/log (single probe).

---

## 7.1. Delivery queue — Redis **Streams** (`kactus_notification/queue.py`)

Retry ở §7 chạy **inline trong request**: một Zalo lag giữ request hàng chục giây cho một kết quả caller không làm gì được. `POST /{id}/send` giờ `XADD` rồi trả `202`.

**Streams chứ không pub/sub.** `PUBLISH` không có trí nhớ — consumer restart đúng giây publish là mất vĩnh viễn, và không chỗ nào ghi lại. Mất một alert giá của user là lỗi thật. (Nudge SSE thì ngược lại: browser refetch, mất một cái không tốn gì → pub/sub đúng.)

**Ack semantics là toàn bộ thiết kế:**

| Handler | Kết quả |
|---|---|
| return | `XACK` — xong |
| **raise** | **không ack** → entry nằm pending → `reclaim_stale()` (XPENDING + XCLAIM) replay |
| quá `notification_queue_max_deliveries` | ack + log ERROR — không có cap thì payload luôn crash sẽ loop vô hạn |

⚠️ Vì vậy **raise nghĩa là "chưa xử lý được"** (crash, DB chết) — **không** phải "gửi thất bại". Một lần gửi hỏng đã ghi `NotificationLog(FAILED)` là **đã xử lý**, handler phải nuốt; để nó raise thì cả vòng retry chạy lại mãi chừng nào channel còn hỏng, mỗi vòng thêm một dòng audit trùng. Xem `kactus_fin/notification/consumer.py::deliver`.

**Consumer chạy ở đâu:** mỗi worker kactus-fin một cái — **lệch plan**, plan đặt ở data plane vì nó single-replica. Lý do đổi: (1) consumer group *chia* entry chứ không broadcast, nên N worker = N sender + tự failover, single-replica là phương án yếu hơn; (2) `kactus-data-plane` cố ý không phụ thuộc `kactus-notification` (xem `deploy/Dockerfile.data-server`), đặt consumer ở đó là kéo `zlapi` vào image ETL — đúng thứ Phase 0.6 vừa gỡ khỏi kactus-common; (3) sender + channel row + `NotificationLog` vốn đã ở process này. Vẫn không phát sinh service thứ tư.

`POST /{id}/test` giữ **đồng bộ**: user đang ngồi trước form credential chờ câu trả lời, `202` ở đó không trả lời gì.

Stream có `maxlen` (trim gần đúng) — nó là **buffer**, không phải audit. `NotificationLog` ở Postgres mới là sự thật.

Settings: `notification_queue_enabled`, `notification_queue_maxlen=10000`, `notification_queue_batch=10`, `notification_queue_block_ms=5000`, `notification_queue_claim_idle_ms=60000`, `notification_queue_max_deliveries=5`. Cần `coordination_backend=redis`; backend `memory` thì gửi inline (dev/test không cần broker).

---

## 7.2. Action link — `kactus_fin/action/`

`NotificationEvent.url` **đã có sẵn** và cả 3 template đã render → lớp notification **không sửa gì**.

Token = `<id>.<HMAC-SHA256>` ký trên id + user + action + params. Chữ ký chứng minh hai việc: không ai giả mạo link, **và** vì params nằm ở DB cũng được ký nên một dòng bị sửa sau khi phát hành sẽ không verify nữa. Snowflake id đoán được, nên chữ ký là thứ chịu lực chính chứ không phải id khó đoán.

`KACTUS_ACTION_TOKEN_SECRET` **fail closed**: `compare_digest("","")` là True, coi secret rỗng như "ký bằng rỗng" sẽ nhận **mọi** token kể cả token không ai phát hành — deployment hỏng mà nhìn như đang chạy.

⚠️ **`GET /api/actions/{token}` không thực thi.** Telegram/Slack/Zalo đều fetch URL ngay khi nó xuất hiện trong tin nhắn để render preview — chưa ai bấm gì. `GET` mà thực thi thì mọi notification actionable sẽ tự chạy lúc được gửi, ký đúng, gán đúng user. `GET` render trang xác nhận; chỉ `POST` (form trên trang đó submit) mới consume.

One-time bằng **conditional UPDATE** (`WHERE consumed_at IS NULL`), không phải read-modify-write: hai POST đồng thời đều qua được check trong `resolve()` và đều chạy. DB chọn người thắng, người thua nhận 409 y như double-click.

`execute()` **consume trước rồi mới chạy handler**: handler hỏng giữa chừng không được để lại link còn sống chạy lại phần nó đã kịp làm.

| Tình huống | Mã |
|---|---|
| Sai chữ ký / token người khác | 403 |
| Dùng lại lần hai | 409 |
| Hết hạn (TTL 15') | 410 (`GoneError`) |

Cả hai verb **yêu cầu session**: token là *pre-authorisation*, không phải credential — ai cầm được link (forward, group chat) vẫn phải đang đăng nhập đúng user.

`POST /api/actions` mint link cho **session user**, không nhận `user_id` từ body.

Handler trong `action/registry.py`, chặn bởi allow-list `ActionType`: `portfolio.add_item`, `portfolio.remove_item`, `portfolio.refresh`, `notification.mute_channel`. **Cố ý không có mua/bán** — repo không có domain khớp lệnh, khai `trade.buy` mà không có gì đứng sau là nói dối đúng chỗ user tin nhất.

---

## 8. Mã hoá secret

`config` là cột `EncryptedJSON` (Fernet, `settings.encryption_key`) → session token/webhook/cookie **không bao giờ** lưu plaintext. Ra API thì `mask_config(type, config)` thay secret bằng `***` theo `SECRET_FIELDS`.

---

## 9. Zalo PA onboarding (QR login)

Port 5 bước reorc `auth.py`, chạy trên `id.zalo.me` bằng `curl_cffi impersonate="chrome"` (proxy ở non-dev):

1. `generate_qr` → GET `/account` (cookies) + POST `/authen/qr/generate` → `{code, image}`.
2. `wait_for_scan` → long-poll `/authen/qr/waiting-scan`; `status=4` = QR bị xoay (`refreshed`) → đổi ảnh, tiếp tục poll.
3. `wait_for_confirm` → long-poll `/authen/qr/waiting-confirm`.
4. `complete_login` → theo redirect bắt `zpw_sek` → dựng `ZlapiAsync` → `getSecretKey` + `fetchAccountInfo` → giữ session hoàn tất trong **in-process TTL store** keyed by `session_id`.
5. **Pick recipient** → `fetchAllFriends` + `fetchAllGroups`/`fetchGroupInfo` → `[{id, name, avatar, is_group}]`; user chọn → tạo `NotificationChannel(channel_type=zalo_pa)` với `ZaloPAChannelConfig`.

Gửi: `send(Message(text), thread_id, ThreadType.USER|GROUP)` (thread_type 0=user, 1=group).

### Caveats (⚠️ phải nhớ)
- **Không chính thức → rủi ro khoá tài khoản**; có thể vỡ khi Zalo đổi.
- **Residential proxy** bắt buộc ở non-dev (`KACTUS_ZALO_PA_PROXY_URL`); datacenter IP/TLS bị chặn.
- **Session hết hạn** → send/test raise `ExternalServiceError` (non-retryable) → re-login = quét QR lại → `reauth`.
- ~~**Single-worker**~~ → **đã gỡ**: QR-session store chạy trên Redis + TTL (Fernet-encrypted) khi `KACTUS_COORDINATION_BACKEND=redis`, nên 5 bước QR có thể rơi vào các worker khác nhau. Client vẫn dựng lại mỗi lần gửi — Zalo PA không ngậm connection nào, nên không có gì để "sở hữu".

---

## 10. API surface

**Generic (`/api/notifications`, dùng chung mọi kênh):**

| Method | Path | Purpose |
|--------|------|---------|
| POST | `` | Tạo kênh (telegram/slack — config gõ trực tiếp) |
| GET | `` | List kênh của user |
| GET | `/{id}` | Chi tiết (secret masked) |
| PUT | `/{id}` | Sửa name/is_active/config |
| DELETE | `/{id}` | Xoá mềm |
| POST | `/{id}/test` | Kiểm tra credentials |
| POST | `/{id}/send` | **Enqueue** vào Redis Stream → trả `202` ngay (§7.1). Backend `memory` thì gửi inline, vẫn `202` |
| GET | `/{id}/logs` | Lịch sử gửi (`Pagination[NotificationLogSchema]`, `limit`) |

**Zalo PA (`/api/notifications/zalo-pa`, chỉ bước có credential):**

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/qr/generate` | → `{session_id, code, image_url}` |
| GET | `/qr/{sid}/scan` | long-poll → scanned/refreshed/expired |
| GET | `/qr/{sid}/confirm` | long-poll → confirmed/rejected |
| POST | `/qr/{sid}/complete` | finalize login → giữ session |
| GET | `/sessions/{sid}/recipients?query=` | picker friends+groups |
| POST | `/channels` | tạo `NotificationChannel` (server dựng config) |
| PUT | `/channels/{id}/reauth` | refresh session sau re-scan (giữ recipient) |

List/get/update/delete/test/send của kênh zalo_pa dùng route **generic**.

---

## 11. Frontend (`frontend/packages/bloom-app`)

Clone `modules/portfolio/`. Stack thực tế: React 18 + Vite 6 + **Radix + Tailwind v4 + CVA**, axios `apiClient` (`ApiResponse<T>`), TanStack Query v5 (key factory), `sonner`, i18next (vi/en). *(Bỏ qua `.claude/rules/frontend-*.md` — chúng mô tả project "usonia" Mantine, sai với bloom.)*

- `types/notification.ts`, `services/notificationService.ts`, `hooks/useNotificationQuery.ts`.
- `modules/notification/pages/`: `NotificationListPage` (bảng kênh + tạo + "reconnect" cho zalo), `NotificationDetailPage` (sửa + test + send + **lịch sử**).
- `modules/notification/components/`: `ChannelFormDialog` (chọn loại; Zalo mở `ZaloPAQRDialog`), `ZaloPAQRDialog` (generate → poll scan (swap ảnh khi refreshed) → poll confirm → complete → `ZaloRecipientPicker`), `ZaloRecipientPicker`, `SendTestDialog`, `ChannelLogTable`.
- Routing: `/notifications`, `/notifications/:id` trong `App.tsx`; sidebar `Bell` trong `DashboardLayout.tsx`; i18n `notification.*` + `nav.notifications`.

---

## 12. Gotchas

- `Notifier.send_event` **cần `session`** (arg đầu) — nó tự ghi log. Caller cũ phải cập nhật.
- `impl.retryable_exceptions` được check **trước** `ExternalServiceError` — đảm bảo `ExternalServiceError` không nằm trong tuple retryable của bất kỳ channel nào.
- Zalo `thread_type`: 0=user, 1=group (khớp `ThreadType`).
- QR-session store: **in-process** (`memory`) hoặc **Redis + TTL** (`redis`) — chỉ backend `memory` mới ràng buộc single-worker. Interface là **async** (`await get_session_store().load(...)`).
- Frontend numeric ids là **string** (FancyInt → string).

---

## 13. Checklist

- [x] const: `NotificationLogStatus`, `NotificationTrigger`, `ZALO_PA`
- [x] model: `NotificationLog` (+ migration)
- [x] service: `NotificationLogService`
- [x] dispatcher: retry/backoff + log + per-channel `retryable_exceptions`
- [x] schema: `ZaloPAChannelConfig`, `NotificationLogSchema`, QR/recipient schemas, `SECRET_FIELDS`
- [x] zalo_pa.py: QR login + session store + `ZlapiAsync` + sync helpers
- [x] channel/template/registry: `ZaloPAChannel` + `ZaloPAEventTemplate`
- [x] API: `GET /{id}/logs` + zalo-pa router (register trong `app.py`)
- [x] config/env: retry settings + `zalo_pa_*`
- [x] tests: dispatcher retry/log, log service, zalo_pa unit, zalo API
- [x] frontend module + routing + nav + i18n (`tsc -b` + `vite build` xanh)
- [x] docs

---

## 14. As-built (khác blueprint)

- Không tạo `NotificationZaloPAAccount` — dùng chung `NotificationChannel` (theo yêu cầu). PA session + recipient nằm trong `ZaloPAChannelConfig`.
- `list_recipients` là seam optional trên `BaseNotificationChannel`; picker chính chạy trên **session store** (`list_session_recipients`) trước khi có channel row.
- `Notifier.test` giữ nguyên (không retry/log).

## 15. Deferred (TODO)

- **Event-driven auto-fire** (handler `data_refreshed`/price-alert → `send_event(trigger=EVENT)`). `trigger=EVENT` đã xuyên suốt log + queue, chỉ thiếu producer.
- **Handler mua/bán cho action link** — repo chưa có domain khớp lệnh, nên `ActionType` cố ý không khai; thêm 1 member + 1 handler khi có tích hợp môi giới.
- Telegram inline keyboard / Slack Block Kit button — cả hai POST về **cùng** `/api/actions/{token}` nên là *thêm*, không phải *sửa*.
- Multi-recipient từ 1 QR session; Zalo attachment/sticker/reply; E2E history (reorc `sync/`+WASM) nếu cần inbound; Discord/Email.

## 16. Cách chạy / verify

```bash
.venv/bin/python -m pytest libs/core/kactus-common/tests services/kactus-fin/tests -q   # 337 pass
.venv/bin/python manage.py fin db upgrade      # tạo notification_logs (cần Postgres)
cd frontend/packages/bloom-app && npx tsc -b && npx vite build   # xanh
```

**Live smoke** (chưa chạy): Telegram — tạo kênh, `/send`, xác nhận nhận + log `success`. Zalo PA — quét QR (qua proxy) → chọn friend/group → tạo kênh → `/send` → xác nhận báo cáo tới + log `success`; ép session hết hạn → `error` (non-retryable) + log `failed`.
