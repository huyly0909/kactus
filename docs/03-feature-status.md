# Feature Status — Kactus & Kactus Bloom

## ✅ Features đã hoàn thành

### Backend — `kactus`

#### 1. Infrastructure & Architecture
- [x] **Monorepo structure** — uv workspaces với 4 packages (common, data, fin, fin-gateway)
- [x] **Settings chain** — BaseKactusSettings → CommonSettings → DataSettings → Settings, hỗ trợ `.env`
- [x] **Settings registry** — Shared settings qua proxy pattern, không circular imports
- [x] **Feature-based app registration** — `KactusApp` + `AppManager` pattern
- [x] **KactusAPIRouter** — Auto-wrap response trong `ResponseModel<T>`
- [x] **Exception hierarchy** — 13 exception classes, auto-mapping HTTP status codes
- [x] **Database session management** — Async SQLAlchemy, auto-commit/rollback, `@provide_session` decorator
- [x] **Dual database architecture** — PostgreSQL (OLTP) + DuckDB (OLAP)
- [x] **Snowflake ID generation** — Distributed unique IDs
- [x] **Pagination helper** — Generic paginator với ordering, filtering
- [x] **CLI management** — `manage.py` (Typer) entry point cho tất cả packages
- [x] **Docker deployment** — Dockerfiles + Docker Compose cho dev/stag/prod
- [x] **Pre-commit hooks** — flake8 linting
- [x] **Logging** — Loguru structured logging

#### 2. Authentication & Session
- [x] **Session-based auth** — httpOnly cookie, bcrypt password hashing
- [x] **Login / Logout endpoints** — `POST /api/auth/login`, `POST /api/auth/logout`
- [x] **Current user endpoint** — `GET /api/auth/me`
- [x] **Remember me** — Session expiry 7 days (default) / 1 year (remember)
- [x] **Session management** — DB-persisted sessions, IP + user agent tracking
- [x] **Fernet encryption** — CryptoService cho sensitive data (API keys, etc.)

#### 3. Authorization (RBAC)
- [x] **Casbin-based RBAC** — In-memory enforcer, auto-loaded tại startup
- [x] **Permission hierarchy** — `manage` > `write` > `read`, auto-expansion
- [x] **`@permission` decorator** — Declarative endpoint-level authorization
- [x] **Superuser bypass** — Superusers skip tất cả permission checks
- [x] **Project-scoped roles** — User có role khác nhau trong từng project
- [x] **Permission API** — `GET /api/me/permissions` — lấy permissions trong project hiện tại
- [x] **Authorization overview** — `GET /api/admin/authorization` — xem toàn bộ role-permission map

#### 4. User Management (Admin)
- [x] **List users** — `GET /api/admin/users`
- [x] **Create user** — `POST /api/admin/users`
- [x] **Reset password** — `POST /api/admin/users/{id}/reset-password` (random password)
- [x] **Deactivate user** — `POST /api/admin/users/{id}/deactivate`
- [x] **Update role** — `PUT /api/admin/users/{id}/role` (toggle superuser)

#### 5. Project Management
- [x] **CRUD operations** — Create, Read, Update, Delete (logical) projects
- [x] **Project listing** — Regular users thấy projects của mình, superusers thấy tất cả
- [x] **Project membership** — Add/remove members, role assignment
- [x] **Project code uniqueness** — Kiểm tra trùng code khi tạo/update
- [x] **Auto-assign owner** — Creator tự động thành owner khi tạo project
- [x] **Admin project list** — `GET /api/admin/projects` — superuser xem tất cả

#### 6. Data Pipeline (ETL)
- [x] **SyncPipeline pattern** — Composable Source → Transform → Storage pipeline
- [x] **Gold price scraper** — `MihongGoldSource` — giá vàng từ mihong.vn
- [x] **Stock OHLCV data** — `VnstockOHLCVSource` — candlestick data (1m → 1M intervals)
- [x] **Stock listing** — `VnstockListingSource` — danh sách mã niêm yết
- [x] **Financial reports** — `VnstockFinanceSource` — income, balance sheet, cash flow, ratio
- [x] **Company overview** — `VnstockCompanySource` — thông tin công ty
- [x] **DuckDB storage** — UPSERT / APPEND / REPLACE strategies
- [x] **DataSourceProtocol** — Standard interface cho tất cả data sources
- [x] **DuckDB table schema** — Typed column definitions

#### 7. Event System
- [x] **Event dispatching framework** — BaseDispatcher, BaseEventPayload, BaseEventName
- [x] **Typed event names** — StrEnum-based, fully qualified names
- [x] **Handler registration** — Decorator-based handler registration
- [x] **Async + sync handlers** — Support cả async và sync event handlers

#### 8. API Gateway (kactus-fin-gateway)
- [x] **Gateway server** — FastAPI app trên port 17601
- [x] **Health check** — `GET /health`
- [x] **Exception handling** — Shared exception handlers từ kactus-common
- [x] **CORS** — Configured cho cross-origin requests
- [x] **Alembic migrations** — Independent migration chain

---

### Frontend — `kactus-bloom`

#### 1. Infrastructure (✅ migration hoàn tất)

**Đã hoàn thành:**
- [x] **Monorepo structure** — pnpm workspaces + Turborepo (2 packages: bloom-app, bloom-ui)
- [x] **Vite build pipeline** — Dev server + production builds
- [x] **TypeScript strict mode** — Type-safe codebase, path aliases (`@/`, `@modules/`)
- [x] **Testing setup** — Vitest + Testing Library
- [x] **Linting & formatting** — ESLint 9 + Prettier + Husky
- [x] **Docker deployment** — Docker Compose cho dev/stag/prod

**Migration Mantine → Tailwind + shadcn (✅ xong — `grep -r @mantine packages/` = 0 hit):**
- [x] **Tailwind CSS v4** — Installed via `@tailwindcss/vite` plugin (không dùng PostCSS)
- [x] **shadcn/ui configuration** — `components.json` + path aliases
- [x] **Design system CSS** — `index.css` với oklch color system, dark mode default, fintech tokens (gain/loss/warning)
- [x] **shadcn primitives** — Button, Input, Label, Card, Badge, Skeleton, **Dialog, Select, Form, Table, DataTable, ConfirmDialog**
- [x] **i18next** — Dual language (vi + en), `locales/{vi,en}.json`
- [x] **Sonner** — Toast notifications (thay Mantine Notifications)
- [x] **lib/ utilities** — `cn()`, `config.ts`, `locale-format.ts`, `module-core.ts`, `format.ts`
- [x] **Code splitting** — `React.lazy` mỗi route + `manualChunks` (react/query/radix/i18n/chart vendor)
- [x] ~~Mantine components~~ — **Removed** (bloom-ui đã port sang Tailwind/shadcn)
- [x] ~~PostCSS Mantine preset~~ — **Removed** (`postcss.config.cjs` deleted)

#### 2. Authentication UI
- [x] **Login page** — Email + password form (**rewritten as shadcn Card + Input + Button**)
- [x] **Auth guard** — Protected routes, redirect to /login
- [x] **Auth store** — Zustand state cho user info
- [x] **Auto 401 redirect** — Axios interceptor redirect to /login khi session expired
- [x] **Session check** — `GET /api/auth/me` on app load

#### 3. Project Selection
- [x] **Project select page** — `/select-project`
- [x] **Project guard** — Kiểm tra project đã chọn, redirect nếu chưa
- [x] **Project store** — Zustand + cookie persistence (`kactus_project_id`)
- [x] **Project service** — CRUD operations + permission queries

#### 4. Admin Panel ✅ (shadcn — `modules/admin/`)
- [x] **Admin guard** — `AdminGuard` layout route, chỉ superusers (backend vẫn enforce riêng)
- [x] **Admin nav** — Nhóm "Quản trị" trong sidebar, chỉ hiện với superuser
- [x] **User management page** — DataTable + create dialog (Form+zod), toggle role / reset password / deactivate qua `ConfirmDialog`; mật khẩu mới hiện 1 lần + copy
- [x] **Project management page** — List tất cả projects (read-only DataTable)
- [x] **Authorization page** — Role → permission mapping, badge theo act

#### 5. Layout ✅
- [x] **DashboardLayout** — Collapsible sidebar, user avatar, module nav, responsive, `Suspense` cho lazy routes (shadcn/Tailwind)
- [x] **Dashboard home** — `modules/core/dashboard/` — stat cards (portfolios/channels/active) + recent portfolios + quick actions
- [x] **bloom-ui `AppLayout`** — đã port sang Tailwind/shadcn (không còn Mantine)

#### 6. Shared Hooks
- [x] **useAuth** — Login/logout/session management
- [x] **useProject** — Project selection, CRUD
- [x] **usePermission** — Permission checking + data fetching
- [x] **useApi** — Generic API hook
- [x] **useWebSocket** — WebSocket với auto-reconnect

#### 7. Permission System
- [x] **Permission store** — Track permissions per project
- [x] **`hasPermission()` check** — Client-side permission gating
- [x] **Superuser bypass** — Client-side superuser override

---

#### Portfolio feature (multi-asset watchlist + ETL/cron + SSE) ✅

Đầy đủ blueprint [04-portfolio-feature.md](04-portfolio-feature.md). 280 backend tests pass; frontend `tsc -b` + `vite build` xanh. **Verified live 2026-06-18** (curl E2E + key thật): quotes/catalog/refresh/SSE ✅. ⚠️ news/events/ratios/foreign_trade hỏng trên vnstock 3.4.2 — known issues + log: [05-portfolio-verification-log.md](05-portfolio-verification-log.md).

- [x] **kactus-common** — models (`portfolios`, `portfolio_items`, `supported_assets`, `crawl_runs`) + service (`get_union_codes_by_type`, catalog, crawl-run dedup) + `events` + `sse/broker.py` + `symbol_provider` Protocol
- [x] **kactus-data** — batch market sources (price_board/news/events/foreign/ratios + catalog VN30/VN100) + `AssetProvider` registry (STOCK→vnstock, GOLD→mihong, COIN defer) + `jobs/crawl.py` + `jobs/scheduler.py` (APScheduler) + CLI `data portfolio`
- [x] **kactus-fin** — `portfolio/api.py` (user-owned CRUD, items, quotes/news, refresh dedup, SSE `/stream`) + admin + lifespan wiring (auth → SSE handler → scheduler) + Alembic `a1b2c3d4e5f6`
- [x] **kactus-bloom** — service + hooks (`usePortfolioQuery`, `useMarketStream`) + list/detail pages + i18n (vi+en) + route/sidebar
- [x] **Phase 0** — `vnstock_api_key`/`mihong_xsrf_token` config + `init_vnstock_auth` + DuckDB `register(df)` (text-safe)
- [x] Verify live với key thật — quotes/catalog/refresh/SSE ✅ (xem [05](05-portfolio-verification-log.md))
- [ ] Fix decision-support kinds (news/events/ratios/foreign_trade) — vnstock 3.4.2 hỏng, cần đánh giá nâng 4.0.4
- [ ] Fix `fin user create-admin` (CLI quên register settings)

#### Notification feature (multi-channel push: Telegram/Slack/Zalo PA) ✅

Đầy đủ blueprint [06-notification-feature.md](06-notification-feature.md). 337 backend tests pass; frontend `tsc -b` + `vite build` xanh. Chưa live-smoke (cần token Telegram + quét QR Zalo + proxy).

- [x] **kactus-notification** (`libs/kactus-notification`, tách khỏi `kactus-common` — xem [06](06-notification-feature.md#3-kiến-trúc)) — 1 model dùng chung `NotificationChannel` (`config` `EncryptedJSON`, per-type Pydantic schema) + `NotificationLog` (append-only) + service (channel + log) + `Notifier` (retry/backoff + log) + channel/template/registry (Telegram/Slack/**ZaloPA**) + `zalo_pa.py` (QR login + `zlapi` wrapper + in-process session store) + `NotificationSettings` mixin
- [x] **kactus-fin** — `notification/api.py` (user-owned CRUD, test, send, `GET /{id}/logs`) + `zalo_pa_api.py` (QR onboarding, recipient picker, zalo channel create/reauth) + Alembic `c3d4e5f6a7b8` (`notification_logs`)
- [x] **kactus-bloom** — `modules/notification/` (service + hooks + list/detail pages + ChannelForm/QR/RecipientPicker/SendTest/LogTable + i18n vi+en + route/sidebar)
- [x] Synchronous bounded retry + send-history audit
- [x] Zalo PA (unofficial, QR login, session-in-config, residential proxy, text-only) — ⚠️ suspension risk
- [ ] Live smoke (Telegram + Zalo PA thật)
- [ ] Event-driven auto-fire (deferred — `trigger=EVENT` đã luồn sẵn qua log)

#### Market feature (gold / stock / finance reads) ✅

REST API đọc thẳng các bảng OLAP (DuckDB) do ETL kactus-data ghi — không có ETL mới, không có bảng mới. 366 backend tests pass (12 test riêng cho market); frontend `tsc -b` + `vite build` + vitest xanh. Chưa live-smoke với DuckDB có dữ liệu thật.

- [x] **kactus-common/data** — `DatabaseClient.execute(sql, params)` + `DuckDBStorage.query(sql, params)` nhận positional params (hết nội suy chuỗi cho giá trị từ client)
- [x] **kactus-fin** — `market/` (`api`/`app`), `KactusApp(name="market", session_routes=[router])`. Sau khi tách data plane: `olap.py` bị xoá, `const`/`schema` lên `kactus_common/market/`, `service.py` xuống `kactus_data/market/`; mỗi endpoint chỉ `await data_client.X(...)`
- [x] **Endpoints** — `GET /api/market/gold`, `/stocks` (search), `/stocks/quotes`, `/stocks/{symbol}`, `/stocks/{symbol}/ohlcv`, `/stocks/{symbol}/news`, `/stocks/{symbol}/finance`
- [x] **Đọc blocking → `asyncio.to_thread`**, limit bị chặn trần (`MAX_LIMIT=2000`), bảng chưa crawl = list rỗng chứ không 500
- [x] **kactus-bloom** — `modules/market/` (Gold board, Stock list + detail có chart recharts + news, Finance pivot theo kỳ) + `useMarketQuery` + i18n vi+en + route/sidebar
- [ ] Live smoke sau khi chạy crawl thật (bảng OHLCV/finance hiện phụ thuộc lịch ETL)
- [ ] Realtime cho market pages (hiện chỉ portfolio có SSE)

## 🚧 Features đang làm (In Progress)

| Area | Feature | Trạng thái | Ghi chú |
|------|---------|-----------|---------|
| Frontend | **Module-based architecture** | 🚧 Foundation | `defineAppModule` + `module-core.ts` created, modules skeleton pending |
| Frontend | **i18n (vi + en)** | 🚧 Setup done | `i18n.ts` + locale files created, not yet wired vào tất cả components |
| Backend | **Event system integration** | 🚧 Framework done | Handlers chưa implement |
| Backend | **Background services** | 🚧 Khai báo chưa implement | `background_services` field có `# TODO: here` |
| Frontend | **WebSocket integration** | 🚧 Hook ready | Chưa có backend WS endpoint (portfolio dùng SSE) |
| Backend | **Gateway features** | 🚧 Skeleton | Chỉ có health check |
| Backend | **Coin data source** | 🚧 Module tạo rồi | Chưa implement (COIN provider defer trong portfolio) |

---

## 📋 Features cần làm (TODO / Planned)

### High Priority — Frontend Architecture (Builtiful Patterns)

| # | Feature | Mô tả | Status |
|---|---------|-------|--------|
| 1 | **Form System** | `Form` + `FieldRow` + `useAppForm` (explicit zod, adapted from Builtiful) | Skeleton |
| 2 | **Entity Page** | `EntityPage` 3-region layout (header/body/footer) | Skeleton |
| 3 | **Data View** | Schema-driven table — `components/ui/data-table.tsx` (TanStack Table + search + pagination) | ✅ Done |
| 4 | **ConfirmDialog** | `components/ui/confirm-dialog.tsx` (shadcn Dialog, destructive variant) | ✅ Done |
| 5 | **Error Bridge** | `applyKactusErrors()` — map Axios errors → RHF field errors | Skeleton |
| 6 | **Module Registry** | `defineAppModule` + auto-discovery via `import.meta.glob` | Skeleton |
| 7 | **Admin pages** | User/Project/Authorization pages (shadcn, `modules/admin/`) | ✅ Done |
| 8 | **Dashboard** | Dashboard home với dữ liệu thật (portfolios + channels) | ✅ Done |

### High Priority — Core Business Logic

| # | Area | Feature | Mô tả | Status |
|---|------|---------|-------|--------|
| 9 | Backend | **Gold price API** | `GET /api/market/gold` — bảng giá vàng từ DuckDB | ✅ Done |
| 10 | Backend | **Stock data API** | `/api/market/stocks{,/quotes,/{symbol},/ohlcv,/news}` | ✅ Done |
| 11 | Backend | **Financial report API** | `GET /api/market/stocks/{symbol}/finance` | ✅ Done |
| 12 | Frontend | **Gold dashboard** | `GoldPricesPage` — bảng giá + spread + nguồn/thời điểm | ✅ Done |
| 13 | Frontend | **Stock dashboard** | `StockMarketPage` + `StockDetailPage` (chart lịch sử giá + news) | ✅ Done |
| 14 | Frontend | **Financial analysis** | `FinancePage` — pivot chỉ tiêu × kỳ, chọn loại báo cáo/kỳ | ✅ Done |

### Medium Priority — Platform Features

| # | Area | Feature | Mô tả |
|---|------|---------|-------|
| 15 | Backend | **Scheduled data sync** | Cron jobs tự động sync dữ liệu |
| 16 | Backend | **WebSocket server** | Real-time push dữ liệu giá vàng/chứng khoán |
| 17 | Backend | **Gateway API routes** | Expose public APIs qua gateway |
| 18 | Backend | **Coin data source** | Implement crypto price data source |
| 19 | Frontend | **Real-time updates** | WebSocket integration cho live price feeds |
| 20 | Frontend | **User profile page** | Trang profile, đổi password |

### Low Priority — Enhancement & Ops

| # | Area | Feature | Mô tả |
|---|------|---------|-------|
| 21 | Frontend | **Dark/Light theme toggle** | User-selectable theme (dark default, light override via `.light` class) |
| 22 | Backend | **Rate limiting** | Implement rate limiter |
| 23 | Backend | **Audit logging** | Track user actions |
| 24 | Frontend | **Export/Download** | Export charts, data to CSV/PDF |
| 25 | Both | **CI/CD pipeline** | Automated testing, deployment |

---

## Package-level Feature Summary

### `kactus-common` — ✅ Mostly Complete
- Database clients (PostgreSQL async + DuckDB)
- Authentication middleware (session-based)
- Authorization (Casbin RBAC)
- Exception handling
- Event framework
- Schema utilities (ResponseModel, Pagination, BaseSchema)
- Crypto services
- Logging

### `kactus-data` — ✅ Core Done, 🚧 Needs More Sources
- SyncPipeline framework hoạt động
- 5 data sources implemented (Gold, Stock OHLCV, Stock Listing, Finance, Company)
- DuckDB storage operational (chỉ được mở read-write bởi `kactus-data-server`)
- ❌ Coin source chưa implement
- ✅ Scheduled sync — APScheduler trong `services/kactus-data-server`
- ❌ Sync history/retry chưa có

#### Data plane / control plane split ✅

Tách `services/kactus-data-server` (port 17602) khỏi `kactus-fin`. 479 backend tests pass; `uv run lint-imports` KEPT cả 2 contract. ⚠️ **Chưa build được Docker image** (Docker daemon không chạy trên máy dev) — compose chỉ mới validate bằng `docker compose config`.

- [x] **kactus-data-server** — `config`/`app`/`runtime` (`DataRuntime`: DuckDB + providers + scheduler)/`security` (`X-Service-Token`, `hmac.compare_digest`, unset token = fail closed)/`symbol_provider` (`WatchlistSymbolProvider` đọc thẳng Postgres) + CLI (**không có** `--workers`, cố định 1)
- [x] **`/internal` API** — `market/*` (7 endpoint ↔ 7 method `MarketService`), `assets/{asset_type}/{kind}` (thay cả 3 chỗ `provider.read`), `crawl`, `catalog/sync`, `scheduler/status`. `/health` là route duy nhất không cần token
- [x] **kactus-fin** — `data_client.py` (httpx pool + token + timeout, lỗi → `ExternalServiceError`/502, **không** trả `[]`), bỏ dependency `kactus-data`, xoá `olap.py`/`portfolio/runtime.py`/`portfolio/symbol_provider.py`/`portfolio/sse.py`
- [x] **import-linter** — thêm contract `forbidden`: `kactus_fin` ✗→ `kactus_data`, `duckdb` (contract `layers` một mình vẫn cho services → libs)
- [x] **Deploy** — `Dockerfile.data-server` + 3 compose; volume DuckDB **chỉ** gắn cho data plane; port 17602 chỉ publish ở dev; `kactus-fin` trở lại 4 worker (prod) / 2 (stag)
- [ ] `docker compose build` + live smoke 3 env

### `kactus-fin` — ✅ Auth/Admin/Portfolio/Notification/Market Done
- Auth module hoàn chỉnh
- Admin module hoàn chỉnh
- Project CRUD hoàn chỉnh
- Permission system hoàn chỉnh
- Portfolio + Notification hoàn chỉnh
- **Market module** — expose gold/stock/finance từ DuckDB qua `/api/market/*` ✅
- ❌ Chưa có WebSocket endpoints (portfolio dùng SSE)

### `kactus-fin-gateway` — 🚧 Skeleton Only
- Server chạy được
- Chỉ có health check endpoint
- ❌ Chưa có public API routes

### `bloom-ui` — ✅ Mantine-free shared lib (chưa được bloom-app dùng)
- Component library (AppLayout, ChartCard, DataTable, ChatBox) — **đã port sang Tailwind/shadcn**
- `useNotification` → sonner; `theme/index.ts` → token object thuần (không còn Mantine)
- Hooks, services, stores — **migrated to bloom-app** (`src/hooks/`, `src/services/`, `src/store/`)
- ⚠️ bloom-app hiện vẫn giữ bản shadcn primitives riêng, **chưa** consume `@kactus-bloom/ui` (hợp nhất là việc sau)

### `bloom-app` — ✅ shadcn/Tailwind, feature-complete cho các module hiện có
- **Stack**: Tailwind v4 + shadcn/ui + i18next + Sonner + TanStack Query/Table + recharts
- **Design system**: oklch colors, dark mode default, fintech tokens
- **shadcn primitives**: button, input, label, card, badge, skeleton, dialog, select, form, table, data-table, confirm-dialog ✅
- **Auth**: Login page (shadcn), auth guards working ✅
- **Layout**: DashboardLayout (collapsible sidebar, Suspense cho lazy routes) ✅
- **Pages**: Dashboard, Portfolio, Notification, Admin (users/projects/authorization), Market (gold/stocks/finance) ✅
- **Perf**: route-level `React.lazy` + vendor `manualChunks` ✅
- **i18n**: vi + en locale files, i18next configured ✅
- **Modules**: `defineAppModule` + `module-core.ts` ready ✅
- ❌ Form system (useAppForm, FieldRow) — skeleton only (RHF+zod dùng trực tiếp qua shadcn `Form`)
- ❌ EntityPage pattern — skeleton only
- ❌ Test coverage mỏng (data-table + format helpers)
