# Portfolio Feature — Design (Multi-Asset Watchlist + ETL/Cron + SSE)

> **Trạng thái**: 📋 Planned (design only — chưa implement). Đây là blueprint cho lần implement sau.
> **Liên quan**: [01-tech-stack.md](01-tech-stack.md) · [02-workflow.md](02-workflow.md) · [03-feature-status.md](03-feature-status.md) · vnstock reference: [../packages/kactus-fin/docs/vnstock/README.md](../packages/kactus-fin/docs/vnstock/README.md), [data-collection.md](../packages/kactus-fin/docs/vnstock/data-collection.md)

---

## 1. Tổng quan

Thêm feature **`portfolio`**: user tạo các **watchlist** chứa nhiều loại tài sản tài chính. Backend chạy **cronjob** crawl dữ liệu thị trường + (với cổ phiếu) tin tức & chỉ số hỗ trợ quyết định cho **union** (hợp) tất cả mã trong portfolio của mọi user, lưu lại, rồi **đẩy SSE** "data refreshed" tới toàn bộ browser đang kết nối để UI tự refetch.

- **Notification** (thông báo): **defer** — hiện chỉ in-app realtime qua SSE, broadcast cho **tất cả** client đang subscribe (chưa filter theo user).
- **Manual refresh**: user bấm nút refresh để trigger crawl thủ công cho 1 portfolio.

### `portfolio` là asset-class agnostic (đa loại tài sản)

Một item được định danh bởi `(asset_type, code)`:

| asset_type | Ví dụ code | Nguồn dữ liệu | Trạng thái |
|------------|-----------|---------------|-----------|
| `STOCK` | `FPT`, `VCB` | `vnstock` (đã tích hợp một phần ở kactus-data) | ✅ ưu tiên, đầy đủ nhất |
| `GOLD` | `SJC`, `999` | `MihongGoldSource` (đã có sẵn) | ✅ tái dùng source có sẵn |
| `COIN` | `BTC`, `ETH` | provider tương lai (vnstock MSN / nguồn khác) | ⏸️ **defer** |

Cổ phiếu là loại tài sản đầu tiên & giàu dữ liệu nhất; vàng tái dùng source có sẵn; coin là provider tương lai. Model + ETL xây quanh một **asset-type strategy** để thêm loại tài sản mới mà **không đổi schema**.

### Phân tách package (theo yêu cầu)

| Lớp | Package | Nội dung |
|-----|---------|----------|
| ETL / core / cron | `kactus-data` | Sources, crawl jobs, scheduler |
| Config / API / tương tác user | `kactus-fin` | Router, app, scheduler wiring, SSE endpoint |
| Domain model + infra dùng chung | `kactus-common` | Models, schema, service, SSE broker, events (theo convention `project`/`user`) |
| UI | `kactus-bloom` | Pages, hooks, SSE client |

Tuân thủ dependency một chiều: `kactus-fin → kactus-data → kactus-common` (không bao giờ ngược). `kactus-data` **không** import code portfolio — nhận `list[str]` mã qua một callback được inject.

---

## 2. Quyết định đã chốt

- **Single-worker v1**: APScheduler in-process + SSE broker in-process; **chưa dùng Redis**. Jobs viết theo kiểu host-agnostic để sau này chuyển sang Celery+Redis worker dễ dàng. Deploy bằng Docker (1 replica fin chạy scheduler).
- **Đa tài sản**: STOCK + GOLD chạy được, COIN defer.
- **Catalog cổ phiếu**: sync **toàn bộ** `Listing.all_symbols()` mỗi ngày để validate; **tag VN30/VN100**; user được **nhập mã tay**. **Catalog vàng**: seed sẵn tập nhỏ (SJC, 999, …).
- **Watchlist only** (chỉ membership; không qty/giá vốn). Holdings (P&L) để sau (bảng `Holding` riêng).
- **Decision-support cổ phiếu (cả 4)**: net foreign flow, corporate events, financial ratios, OHLCV + technicals. (Vàng/coin chỉ có giá + lịch sử.)

---

## 3. Kiến trúc tổng quan

```
┌──────────────────────── kactus-bloom (React) ────────────────────────┐
│  Portfolio pages · Asset picker (VN30/VN100 tag) · Quotes table       │
│  News widget · Refresh buttons · useMarketStream (EventSource)        │
└───────────┬───────────────────────────────────────────▲──────────────┘
            │ REST (/api/...)                            │ SSE (/api/portfolios/stream)
            ▼                                            │ nudge: {asset_type, kind, codes}
┌──────────────────────── kactus-fin (FastAPI :17600) ──┴──────────────┐
│  portfolio/api.py  (CRUD, items, catalog, reads, refresh, SSE)       │
│  app.py lifespan:  init vnstock auth → register SSE handler          │
│                    → build_scheduler() + inject SymbolProvider       │
│  APScheduler (in-process, Asia/Ho_Chi_Minh)  →  SSEBroker.publish()  │
└───────────┬──────────────────────────────────────────────────────────┘
            │ inject list[str] theo asset_type (IoC)
            ▼
┌──────────────────────── kactus-data (ETL) ───────────────────────────┐
│  AssetProvider registry:  STOCK→vnstock · GOLD→mihong · COIN→defer    │
│  jobs/crawl.py (anyio.to_thread, Semaphore theo tier) → DuckDBStorage │
│  jobs/scheduler.py (build_scheduler, cron triggers)                   │
└───────────┬──────────────────────────────────────────────────────────┘
            ▼
┌──────────────────────── kactus-common ───────────────────────────────┐
│  portfolio/{model,schema,service,const,events,symbol_provider}       │
│  sse/broker.py (asyncio fan-out)                                      │
│        Postgres (OLTP: intent)        DuckDB (OLAP: market facts)     │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 4. Asset-type strategy (seam generic)

Mỗi `asset_type` có một **`AssetProvider`** định nghĩa:

| Method | Vai trò |
|--------|---------|
| `sync_supported()` | Populate catalog (`supported_assets`) — vd stock: `Listing.all_symbols()` + tag VN30/VN100; gold: seed SJC/999 |
| `crawl(codes)` | Fetch giá + extras đặc thù → store vào DuckDB; ghi `crawl_runs` |
| `read(codes)` | Đọc lại từ DuckDB phục vụ API |

**Registry**: `STOCK → VnstockProvider`, `GOLD → MihongProvider`, `COIN → (defer)`.

Scheduler lấy union các item **gom theo `asset_type`** rồi gọi đúng provider. Thêm loại tài sản mới = thêm 1 provider, không sửa schema/model. Decision-support là **đặc thù theo loại** (cổ phiếu có foreign-flow/ratios/news; vàng chỉ có giá).

---

## 5. Data model — Postgres (OLTP)

Đặt ở `kactus-common` (`kactus_common/portfolio/`), mirror `kactus_common/project/`. Đăng ký module trong `kactus_common/__init__.py` `MODELS`.

| Bảng | Cột chính | Ghi chú |
|------|-----------|---------|
| `portfolios` | `id` (snowflake PK), `name`, `description`, `owner_id` (indexed) | `ModelMixin, AuditMixin, LogicalDeleteMixin`. 1 user : nhiều portfolio. |
| `portfolio_items` | `id`, `portfolio_id` (indexed), `asset_type` (enum STOCK/GOLD/COIN), `code` (str) | `UniqueConstraint(portfolio_id, asset_type, code)`. **Watchlist** (membership). |
| `supported_assets` | `asset_type`, `code`, `name`, `is_crawlable` (bool), `tags` (JSON, vd `["VN30","VN100"]`), `meta_json` (vd `exchange`), `synced_at` | `Unique(asset_type, code)`. Catalog backend offer cho user chọn + validate mã nhập tay. |
| `crawl_runs` | `id`, `asset_type`, `kind`, `trigger` (cron/manual), `portfolio_id` (nullable), `status`, `started_at`, `finished_at`, `rows_written`, `error` | Audit + dedup manual-refresh + observability cho admin. |

**Holdings (defer)**: khi cần P&L, thêm bảng `holdings` riêng (`portfolio_item_id`, `quantity`, `avg_cost`, `currency`) — không nhồi vào `portfolio_items`.

**Service** (`portfolio/service.py`):
- `PortfolioService`: CRUD; `add_item`/`remove_item` (validate vs `supported_assets`); `get_user_portfolios`; `list_all` (admin).
- `get_union_codes_by_type(session) -> dict[AssetType, list[str]]` — `SELECT DISTINCT` qua các item chưa xóa, ∩ `is_crawlable`, gom theo loại. **Đây là cross-package contract** cho cron.

---

## 6. Market data — DuckDB (OLAP)

Giữ nguyên split: **Postgres = ý định của user**, **DuckDB = sự thật thị trường**. Một read "xem portfolio" = Postgres (mã nào) → DuckDB (`WHERE code IN (...)`) dispatch theo provider.

| asset_type | Bảng DuckDB | Trạng thái |
|------------|-------------|-----------|
| STOCK | `stock_price_board` (giá batch), `stock_news`, `stock_foreign_trade`, `stock_ratios`, `stock_events` | **mới** |
| STOCK | `stock_ohlcv` | đã có |
| GOLD | bảng giá vàng (mihong) | đã có |

Tất cả dùng `UpdateStrategy.UPSERT` (key theo `code[+time]`). **Technicals (MA/RSI/MACD)** được **tính tại read** từ `stock_ohlcv`, không crawl.

---

## 7. ETL & Cron (`kactus-data`)

### 7.1 Sources (extend `VnstockSource`, theo precedent import inline trong source)

| Source | vnstock API | Dữ liệu |
|--------|-------------|---------|
| `VnstockPriceBoardSource` | `Trading.price_board(symbols_list=chunk)` | **Batch primitive** — 1 call nhiều mã (chunk ~50). Pin `source`, map cột rõ ràng (KBS 29 cột vs VCI 77 cột). |
| `VnstockForeignTradeSource` | `Trading.foreign_trade` | Net foreign flow |
| (news) | `Company.news()` | Tin tức theo mã |
| (events) | `Company.events()` | Cổ tức, ĐHCĐ, ex-rights |
| (ratios) | `Finance.ratio` | P/E, P/B, ROE, EPS |
| (ohlcv) | `Quote.history` (đã có) | Nến lịch sử |
| `MihongGoldSource` | mihong.vn (đã có) | Giá vàng |

### 7.2 Jobs (`jobs/` — hiện là placeholder rỗng)

- **Portfolio-ignorant**: mọi `crawl_*(codes: list[str], storage)` chỉ nhận list mã.
- Bọc phần blocking (vnstock/pandas/DuckDB) trong `anyio.to_thread.run_sync`.
- Throttle bằng `asyncio.Semaphore` size theo tier (`vnai.get_tier_info()`); ghi `crawl_runs`.
- `scheduler.py build_scheduler()` → `AsyncIOScheduler`; gọi `SymbolProvider` được inject (không biết gì về portfolio).

### 7.3 Crawl cadence

| Dataset | asset_type | Tần suất | Trigger |
|---------|-----------|----------|---------|
| price_board (giá) | STOCK | mỗi giờ trong giờ giao dịch | `CronTrigger(day_of_week="mon-fri", hour="9-15", minute=0, timezone="Asia/Ho_Chi_Minh")` |
| news | STOCK | mỗi giờ (giờ giao dịch) | như trên |
| foreign_trade, ratios, ohlcv(1D), events | STOCK | hằng ngày sau giờ đóng cửa | cron daily |
| `sync_supported` (listing + tag VN30/VN100) | STOCK | hằng ngày trước giờ mở cửa | cron daily |
| giá vàng | GOLD | mỗi giờ | cron hourly |

**Crawl set** = `DISTINCT(portfolio_items.code)` ∪ VN30 ∪ VN100 (baseline cấu hình được), lọc `is_crawlable`. `price_board` gộp toàn bộ mã trong **1 call** nên chi phí gần như O(1) theo số mã.

---

## 8. API surface (`kactus-fin`)

`KactusAPIRouter` (auto-wrap `ResponseModel<T>`), `@provide_session`, `@permission`, `request.state.user`.

| Method · Path | Vai trò |
|---------------|---------|
| `POST/GET /api/portfolios` · `GET/PUT/DELETE /api/portfolios/{id}` | CRUD (superuser xem tất cả, mirror project) |
| `POST/DELETE /api/portfolios/{id}/items` | Add/remove item — validate vs `supported_assets` (chấp nhận mã nhập tay) |
| `GET /api/assets/supported?asset_type=&q=&tag=` | Catalog mã backend offer (kèm tag VN30/VN100) |
| `GET /api/portfolios/{id}/quotes` · `/news` | Đọc dữ liệu thị trường đã crawl (Postgres → DuckDB) |
| `GET /api/assets/{type}/{code}/ohlcv|foreign-trade|ratios|events` | Decision-support reads |
| `POST /api/portfolios/{id}/refresh` (và `/news/refresh`) | Manual refresh — **dedup** với `crawl_runs` đang chạy → one-shot `scheduler.add_job(next_run_time=now)` |
| `GET /api/crawl-runs/{id}` | Poll trạng thái refresh |
| `GET /api/portfolios/stream` | **SSE** — broadcast nudge cho tất cả subscriber |
| `GET /api/admin/portfolios` · `/crawl-runs` · `/crawl/status` · `POST /crawl/run-now` · `/assets/sync` | Admin (superuser) |

**`app.py` lifespan (thứ tự quan trọng)**:
1. `init_vnstock_auth(settings)`.
2. **Đăng ký SSE handler `@register_handler(MarketEventName.data_refreshed)` TRƯỚC khi start scheduler** (blinker raise `KeyError` nếu dispatch event chưa có handler).
3. `build_scheduler()` + inject `SymbolProvider` (mở session fin → `get_union_codes_by_type` ∪ baseline VN30/VN100) → start; stop khi shutdown.

Event hoàn tất crawl dispatch ở **foreground/blinker** (`background=False`) — `background=True` (fastapi-events) **no-op im lặng** ngoài request context.

---

## 9. SSE realtime flow

```
Cron/manual crawl xong (kactus-data)
   └─ dispatch MarketDataRefreshed{asset_type, kind, codes, crawl_run_id}  (foreground/blinker)
        └─ fin handler  →  SSEBroker.publish(nudge)
              └─ mọi EventSource client nhận nudge
                    └─ TanStack Query invalidate keys liên quan  →  refetch REST
```

- **SSEBroker** (`kactus_common/sse/broker.py`): `dict[client_id, asyncio.Queue]`, `subscribe()`/`unsubscribe()`/`publish()`, **bounded queue / drop-oldest** chống slow client. Interface swap được sang Redis pub/sub sau.
- Endpoint trả `EventSourceResponse` — **bắt buộc set `response_class=EventSourceResponse`** (hoặc `response_model=None`) để `KactusAPIRouter` **không** wrap/làm hỏng stream. Heartbeat ping ~15s.
- Payload chỉ là **nudge nhẹ** ("có thay đổi → refetch"), không stream dữ liệu giá → reconnect đơn giản (client refetch REST).
- Lưu ý: hiện đã có hook `useWebSocket` + kế hoạch WS server (xem [03-feature-status.md](03-feature-status.md)); feature này chọn **SSE** vì chỉ cần broadcast một chiều nhẹ.

---

## 10. Wiring API key vnstock

vnstock **không** đọc env var trực tiếp; auth qua package **`vnai`**.

1. Thêm field vào `DataSettings`: `vnstock_api_key: str = Field("", validation_alias="VNSTOCK_API_KEY")` — vì `env_prefix="KACTUS_"` nên biến `VNSTOCK_API_KEY` (bare) trong [../packages/kactus-data/.env](../packages/kactus-data/.env) **chỉ bind được khi có `validation_alias`** (nếu không sẽ rơi về guest 20 req/phút).
2. `init_vnstock_auth(settings)`: `import vnai; if key: vnai.setup_api_key(key)` — **dùng `vnai.setup_api_key`, KHÔNG phải `register_user`** (tên đó không tồn tại trong bản cài). Log `vnai.check_api_key_status()` (không bao giờ log key).
3. Rate-limiter (`Semaphore`/token-bucket) size theo `vnai.get_tier_info()` / `get_user_tier()` — guest 20 / free 60 / paid 180–500 req/phút.

---

## 11. Frontend (`kactus-bloom`)

Stack: React 18 + Vite + TanStack Query v5 + Zustand + shadcn/ui + i18next + **sonner** (đã wire ở `main.tsx`). `apiClient` (axios, `withCredentials`, unwrap `{code,msg,data}`) không cần đổi. Hiện **chưa** có TanStack Query hooks hay SSE — feature này lập pattern.

- **shadcn add**: `table`, `dialog`, `command`, `popover` (combobox picker), `select`, `tabs`.
- `services/portfolioService.ts`, `types/portfolio.ts` (asset-generic).
- `hooks/usePortfolioQuery.ts` — `portfolioKeys` factory + `useQuery`/`useMutation` (+ `invalidateQueries`).
- `hooks/useMarketStream.ts` — 1 `EventSource('/api/portfolios/stream', {withCredentials:true})`; nhận `data_refreshed` → invalidate keys quotes/news + optional toast; mount 1 lần ở layout. (SSE đi qua vite proxy `/api` → :17600.)
- `store/portfolioStore.ts` — portfolio đang chọn (cookie-backed, như `projectStore`).
- Pages `modules/portfolio/pages/`: list (cards + create dialog); detail (asset picker combobox có badge VN30/VN100 + filter asset-type, quotes table màu gain/loss + cột foreign/ratios, news widget, **nút refresh icon** cho quotes + news).
- Route + sidebar item ([App.tsx](../../kactus-bloom/packages/bloom-app/src/App.tsx), [DashboardLayout.tsx](../../kactus-bloom/packages/bloom-app/src/layouts/DashboardLayout.tsx)) + i18n `portfolio.*` (vi + en).

---

## 12. Gotchas (đã verify — phải tuân thủ khi implement)

| # | Cạm bẫy |
|---|---------|
| 1 | `import vnstock` **crash** nếu thiếu `pytz`. Thêm deps: `pytz` + `apscheduler` (kactus-data), `sse-starlette` (kactus-fin). |
| 2 | Key qua **`vnai.setup_api_key`** + `validation_alias="VNSTOCK_API_KEY"`; thiếu key → guest 20/phút. |
| 3 | Mọi call vnstock/pandas/DuckDB là **blocking** → `anyio.to_thread.run_sync`, nếu không sẽ chặn event loop + toàn bộ SSE. |
| 4 | Event ở scheduler context: **foreground/blinker**; đăng ký SSE handler **trước** lần dispatch đầu (blinker `KeyError`). |
| 5 | SSE endpoint cần **`response_class`** để bypass `KactusAPIRouter` wrapping. |
| 6 | Manual refresh phải **dedup/coalesce** tránh bão quota khi user bấm liên tục. |
| 7 | Cột `price_board` khác nhau KBS vs VCI — pin source + map cột tường minh. |
| 8 | DuckDB INSERT hiện dùng string-interpolation → chuyển sang `connection.register(df)` cho an toàn với tiêu đề tin tức tiếng Việt (dấu nháy) + nhanh hơn. |
| 9 | **Single-worker** là điều kiện nền (scheduler in-process sẽ double-fire, SSE in-process không cross-worker nếu >1 worker). |

---

## 13. Scalability & migration path

- **Hôm nay (v1)**: 1 process fin (`uvicorn --workers 1`) chứa scheduler + SSE broker; jobs viết host-agnostic.
- **Khi cần scale** (nhiều worker / nhiều instance):
  1. **SSE cross-process** → thay `SSEBroker` transport bằng **Redis pub/sub** (giữ nguyên interface).
  2. **Scheduler** → tách thành worker riêng (`python manage.py data scheduler`) hoặc **Celery beat + worker + Redis**; job functions không đổi, chỉ đổi host trigger. Cần leader-lock để tránh double-fire.
  3. **DuckDB single-writer** → giữ 1 writer (worker), hoặc mirror "latest quote" sang bảng cache Postgres để API không đụng file OLAP trên request path.
- Chi phí crawl scale theo **số mã distinct** (union dedup), không theo số portfolio: 10k portfolio cùng giữ VN30 ⇒ vẫn chỉ ~30 mã.

---

## 14. Implementation checklist (cho lần sau)

- [ ] **Phase 0**: thêm deps (`pytz`, `apscheduler`, `sse-starlette`); wire `vnstock_api_key` (`validation_alias`) + `init_vnstock_auth`; sửa DuckDB INSERT dùng `register(df)`.
- [ ] **kactus-common**: models (`portfolio_items`, `supported_assets`, `crawl_runs`) + schema + service (`get_union_codes_by_type`) + `events` + `sse/broker.py` + `symbol_provider` Protocol; thêm vào `MODELS`.
- [ ] **kactus-data**: sources (price_board, foreign_trade, news, events) + DuckDB tables + `jobs/crawl.py` + `jobs/scheduler.py` + `AssetProvider` registry (STOCK, GOLD) + CLI.
- [ ] **kactus-fin**: `portfolio/api.py` + `app.py` + lifespan wiring (auth → SSE handler → scheduler) + admin + Alembic migration.
- [ ] **kactus-bloom**: services + hooks (`usePortfolioQuery`, `useMarketStream`) + pages + i18n + shadcn components.
- [ ] **Tests**: service union/dedup, sources (mock vnstock), crawl→DuckDB (tmp_path), API (create→add→quotes), manual-refresh dedup, SSE emit; `--cov-fail-under=80`.

---

## 15. References

- vnstock API: [../packages/kactus-fin/docs/vnstock/api-reference.md](../packages/kactus-fin/docs/vnstock/api-reference.md)
- vnstock cron/backfill: [../packages/kactus-fin/docs/vnstock/data-collection.md](../packages/kactus-fin/docs/vnstock/data-collection.md), [backfill-strategies.md](../packages/kactus-fin/docs/vnstock/backfill-strategies.md)
- vnstock auth/tier: [../packages/kactus-fin/docs/vnstock/authentication.md](../packages/kactus-fin/docs/vnstock/authentication.md)
- Feature app pattern & data pipeline: [02-workflow.md](02-workflow.md)
