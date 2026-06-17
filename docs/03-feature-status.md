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

#### 1. Infrastructure (🔄 Đang migration)

**Đã hoàn thành:**
- [x] **Monorepo structure** — pnpm workspaces + Turborepo (2 packages: bloom-app, bloom-ui)
- [x] **Vite build pipeline** — Dev server + production builds
- [x] **TypeScript strict mode** — Type-safe codebase, path aliases (`@/`, `@modules/`)
- [x] **Testing setup** — Vitest + Testing Library
- [x] **Linting & formatting** — ESLint 9 + Prettier + Husky
- [x] **Docker deployment** — Docker Compose cho dev/stag/prod

**Migration Mantine → Tailwind + shadcn (đang làm):**
- [x] **Tailwind CSS v4** — Installed via `@tailwindcss/vite` plugin (không dùng PostCSS)
- [x] **shadcn/ui configuration** — `components.json` + path aliases
- [x] **Design system CSS** — `index.css` với oklch color system, dark mode default, fintech tokens (gain/loss/warning)
- [x] **shadcn primitives** — Button, Input, Label, Card, Badge, Skeleton
- [x] **i18next** — Dual language (vi + en), `locales/{vi,en}.json`
- [x] **Sonner** — Toast notifications (thay Mantine Notifications)
- [x] **lib/ utilities** — `cn()`, `config.ts`, `locale-format.ts`, `module-core.ts`
- [ ] ~~Mantine components~~ — **Removed** (migration in progress)
- [ ] ~~PostCSS Mantine preset~~ — **Removed** (`postcss.config.cjs` deleted)

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

#### 4. Admin Panel (legacy Mantine — cần rewrite)
- [x] **Admin guard** — Chỉ superusers truy cập
- [x] **Admin layout** — Sidebar navigation riêng
- [x] **User management page** — List, create, deactivate, reset password, toggle role
- [x] **Project management page** — List tất cả projects
- [x] **Authorization page** — Xem role-permission mappings

#### 5. Layout (🔄 migrating)
- [x] **DashboardLayout** — Collapsible sidebar, user avatar, module nav, responsive (**new, shadcn/Tailwind**)
- [ ] **Legacy AppLayout** — (cũ, Mantine-based — sẽ bị thay thế bởi DashboardLayout)

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

Đầy đủ blueprint [04-portfolio-feature.md](04-portfolio-feature.md). 280 backend tests pass; frontend `tsc -b` + `vite build` xanh. Chưa verify với dữ liệu vnstock thật.

- [x] **kactus-common** — models (`portfolios`, `portfolio_items`, `supported_assets`, `crawl_runs`) + service (`get_union_codes_by_type`, catalog, crawl-run dedup) + `events` + `sse/broker.py` + `symbol_provider` Protocol
- [x] **kactus-data** — batch market sources (price_board/news/events/foreign/ratios + catalog VN30/VN100) + `AssetProvider` registry (STOCK→vnstock, GOLD→mihong, COIN defer) + `jobs/crawl.py` + `jobs/scheduler.py` (APScheduler) + CLI `data portfolio`
- [x] **kactus-fin** — `portfolio/api.py` (user-owned CRUD, items, quotes/news, refresh dedup, SSE `/stream`) + admin + lifespan wiring (auth → SSE handler → scheduler) + Alembic `a1b2c3d4e5f6`
- [x] **kactus-bloom** — service + hooks (`usePortfolioQuery`, `useMarketStream`) + list/detail pages + i18n (vi+en) + route/sidebar
- [x] **Phase 0** — `vnstock_api_key`/`mihong_xsrf_token` config + `init_vnstock_auth` + DuckDB `register(df)` (text-safe)
- [ ] Verify với key vnstock thật + dữ liệu live (cần server chạy)

## 🚧 Features đang làm (In Progress)

| Area | Feature | Trạng thái | Ghi chú |
|------|---------|-----------|---------|
| Frontend | **Mantine → Tailwind + shadcn migration** | 🚧 Phase 0 | shadcn primitives + design system done, rewriting pages |
| Frontend | **Module-based architecture** | 🚧 Foundation | `defineAppModule` + `module-core.ts` created, modules skeleton pending |
| Frontend | **i18n (vi + en)** | 🚧 Setup done | `i18n.ts` + locale files created, not yet wired vào tất cả components |
| Backend | **Event system integration** | 🚧 Framework done | Handlers chưa implement |
| Backend | **Background services** | 🚧 Khai báo chưa implement | `background_services` field có `# TODO: here` |
| Frontend | **Dashboard real data** | 🚧 UI done, data hardcoded | Cần connect API |
| Frontend | **WebSocket integration** | 🚧 Hook ready | Chưa có backend WS endpoint |
| Backend | **Gateway features** | 🚧 Skeleton | Chỉ có health check |
| Backend | **Coin data source** | 🚧 Module tạo rồi | Chưa implement (COIN provider defer trong portfolio) |

---

## 📋 Features cần làm (TODO / Planned)

### High Priority — Frontend Architecture (Builtiful Patterns)

| # | Feature | Mô tả | Status |
|---|---------|-------|--------|
| 1 | **Form System** | `Form` + `FieldRow` + `useAppForm` (explicit zod, adapted from Builtiful) | Skeleton |
| 2 | **Entity Page** | `EntityPage` 3-region layout (header/body/footer) | Skeleton |
| 3 | **Data View** | Schema-driven table (`ViewSchema` + TanStack Table + toolbar/cells) | Skeleton |
| 4 | **ConfirmDialog** | shadcn Dialog with bullet-point confirmations | Skeleton |
| 5 | **Error Bridge** | `applyKactusErrors()` — map Axios errors → RHF field errors | Skeleton |
| 6 | **Module Registry** | `defineAppModule` + auto-discovery via `import.meta.glob` | Skeleton |
| 7 | **Admin pages rewrite** | Rewrite User/Project/Auth pages from Mantine → shadcn | TODO |
| 8 | **Dashboard rewrite** | Rewrite Dashboard page from Mantine → shadcn | TODO |

### High Priority — Core Business Logic

| # | Area | Feature | Mô tả |
|---|------|---------|-------|
| 9 | Backend | **Gold price API** | Expose giá vàng từ DuckDB qua REST API |
| 10 | Backend | **Stock data API** | Expose dữ liệu chứng khoán (OHLCV, listing) qua REST API |
| 11 | Backend | **Financial report API** | Expose báo cáo tài chính qua REST API |
| 12 | Frontend | **Gold dashboard** | UI hiển thị giá vàng real-time, charts lịch sử |
| 13 | Frontend | **Stock dashboard** | UI hiển thị dữ liệu chứng khoán, candlestick charts |
| 14 | Frontend | **Financial analysis** | UI phân tích báo cáo tài chính |

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
- DuckDB storage operational
- ❌ Coin source chưa implement
- ❌ Scheduled sync chưa có
- ❌ Sync history/retry chưa có

### `kactus-fin` — ✅ Auth/Admin Done, ❌ Business APIs Missing
- Auth module hoàn chỉnh
- Admin module hoàn chỉnh
- Project CRUD hoàn chỉnh
- Permission system hoàn chỉnh
- ❌ Chưa có API expose dữ liệu tài chính từ DuckDB
- ❌ Chưa có WebSocket endpoints

### `kactus-fin-gateway` — 🚧 Skeleton Only
- Server chạy được
- Chỉ có health check endpoint
- ❌ Chưa có public API routes

### `bloom-ui` — 🔄 Legacy (Mantine) → Being replaced
- **Status**: Đang migration sang bloom-app (Tailwind + shadcn)
- Component library (AppLayout, ChartCard, DataTable, ChatBox) — **legacy Mantine code**
- Hooks, services, stores — **migrated to bloom-app** (`src/hooks/`, `src/services/`, `src/store/`)
- Theme system — **replaced** by Tailwind CSS variables + `index.css`

### `bloom-app` — 🚧 Migrating to Builtiful Architecture
- **New stack**: Tailwind v4 + shadcn/ui + i18next + Sonner
- **Design system**: oklch colors, dark mode default, fintech tokens
- **shadcn primitives**: Button, Input, Label, Card, Badge, Skeleton ✅
- **Auth**: Login page rewritten (shadcn), auth guards working ✅
- **Layout**: DashboardLayout rewritten (Tailwind, collapsible sidebar) ✅
- **i18n**: vi + en locale files, i18next configured ✅
- **Modules**: `defineAppModule` + `module-core.ts` ready ✅
- ❌ Admin pages still use legacy Mantine (need rewrite)
- ❌ Dashboard still uses legacy Mantine (need rewrite)
- ❌ Form system (useAppForm, FieldRow) — skeleton only
- ❌ EntityPage pattern — skeleton only
- ❌ DataView pattern — skeleton only
- ❌ Gold/Stock/Finance module pages — not started (waiting for backend APIs + data)

### Migration Progress (Mantine → Tailwind + shadcn)

```
bloom-app src/ file status:
────────────────────────────────
✅ NEW (Tailwind/shadcn)         ❌ LEGACY (Mantine, needs rewrite)
─────────────────────────────── ────────────────────────────────────
components/ui/button.tsx         pages/Admin/*.tsx
components/ui/input.tsx          pages/Dashboard/index.tsx
components/ui/label.tsx          pages/Login/index.tsx (old)
components/ui/card.tsx           pages/ProjectSelect/index.tsx
components/ui/badge.tsx          pages/NotFound/index.tsx
components/ui/skeleton.tsx       pages/Welcome/index.tsx
layouts/DashboardLayout.tsx      router/index.tsx (old router)
modules/core/auth/LoginPage.tsx  router/guards.tsx
lib/utils.ts
lib/config.ts
lib/locale-format.ts
lib/module-core.ts
i18n.ts
locales/{vi,en}.json
```
