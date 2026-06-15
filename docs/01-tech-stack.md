# Tech Stack — Kactus & Kactus Bloom

## Tổng quan kiến trúc

Hệ thống Kactus là một **fintech platform** xử lý dữ liệu tài chính (giá vàng, chứng khoán, báo cáo tài chính), được chia thành 2 repository:

- **kactus** — Backend (Python monorepo)
- **kactus-bloom** — Frontend (TypeScript/React monorepo)

Frontend áp dụng best practices từ dự án **Builtiful** (ERP/POS platform sử dụng PocketBase + Go + React), cụ thể:
- **UI Framework**: Tailwind CSS v4 + shadcn/ui (Radix primitives + CVA variants)
- **Architecture**: Module-based (mirrors Builtiful `modules/<m>/` pattern)
- **Forms**: `useAppForm` + `Form` + `FieldRow` (adapted — không có codegen, explicit zod schemas)
- **Data Views**: Schema-driven table system (`ViewSchema` + TanStack Table)
- **Entity Pages**: `EntityPage` 3-region layout (header/body/footer)
- **i18n**: i18next với per-module locales (vi + en)

> **Key difference from Builtiful**: Builtiful dùng PocketBase với codegen pipeline (`schema.go` → `blueprints.ts`) để auto-derive zod schemas và form fields. Kactus dùng FastAPI/Pydantic backend nên **không có codegen** — TS types và zod schemas phải hand-write. Tất cả patterns vẫn giữ nhưng explicit hơn.

---

## Backend — `kactus` (Python Monorepo)

### Ngôn ngữ & Runtime

| Item | Version |
|------|---------|
| Python | ≥ 3.12 |
| Package Manager | [uv](https://docs.astral.sh/uv/) workspaces |
| Monorepo structure | `uv workspace` (members trong `packages/*`) |

### Framework & Libraries chính

| Category | Library | Vai trò |
|----------|---------|---------|
| **Web Framework** | FastAPI ≥ 0.115 | REST API server (async) |
| **ASGI Server** | Uvicorn (standard) | HTTP server, hot-reload |
| **ORM / Database** | SQLAlchemy 2.0+ (async) | OLTP database (PostgreSQL) |
| **Async DB Driver** | asyncpg | PostgreSQL async driver |
| **Analytics DB** | DuckDB ≥ 1.4 | OLAP database cho dữ liệu tài chính |
| **Data Processing** | Pandas ≥ 3.0 | Data transformation, ETL |
| **Schema / Validation** | Pydantic v2 | Request/response validation, settings |
| **Settings** | pydantic-settings | Environment variables, `.env` loading |
| **Migration** | Alembic | Database schema migration |
| **Auth — Password** | bcrypt | Password hashing (one-way) |
| **Auth — Encryption** | cryptography (Fernet) | Symmetric encryption cho sensitive data |
| **Authorization** | Casbin ≥ 1.36 | RBAC policy enforcement (in-memory) |
| **CLI** | Typer | CLI management (manage.py) |
| **Logging** | Loguru | Structured logging |
| **Serialization** | orjson | Fast JSON serialization |
| **Events** | blinker + fastapi-events | In-process event dispatching |
| **Data Sources** | vnstock ≥ 3.0 | Vietnam stock market data |
| **Data Sources** | requests | HTTP scraping (gold prices) |
| **ID Generation** | snowflake-id | Distributed unique ID |
| **String Utils** | inflect | Pluralization, table naming |
| **DB Utils** | sqlalchemy-utils | Extra SQLAlchemy types/utilities |

### Testing

| Library | Vai trò |
|---------|---------|
| pytest ≥ 8.0 | Test framework |
| pytest-asyncio | Async test support |
| httpx | Test client cho FastAPI |
| aiosqlite | SQLite async driver (test DB) |

### DevOps & Tooling

| Tool | Vai trò |
|------|---------|
| Docker + Docker Compose | Container deployment (dev/stag/prod) |
| pre-commit | Git hooks (lint, format) |
| flake8 | Python linting |

---

## Frontend — `kactus-bloom` (TypeScript/React Monorepo)

### Ngôn ngữ & Runtime

| Item | Version |
|------|---------|
| TypeScript | ≥ 5.7 |
| Runtime / Package Manager | [Bun](https://bun.sh/) ≥ 1.3 (giống Builtiful) |
| Monorepo Orchestrator | Turborepo (turbo ≥ 2.4) |

### Monorepo Structure

```
kactus-bloom/
├── packages/
│   ├── bloom-app/          ← Main application (Vite SPA)
│   │   ├── src/
│   │   │   ├── components/ui/   ← shadcn primitives (button, input, card, ...)
│   │   │   ├── lib/             ← Shared utilities (cn, config, formatting)
│   │   │   ├── layouts/         ← DashboardLayout, AuthLayout
│   │   │   ├── modules/         ← Domain modules (core, dashboard, gold, stock, finance)
│   │   │   ├── store/           ← Zustand stores (auth, project, permission)
│   │   │   ├── services/        ← API services (auth, project, admin)
│   │   │   ├── hooks/           ← Shared hooks (useAuth, ...)
│   │   │   ├── types/           ← TS type definitions
│   │   │   ├── locales/         ← i18n translations (vi.json, en.json)
│   │   │   └── i18n.ts          ← i18next configuration
│   │   ├── components.json      ← shadcn/ui configuration
│   │   └── vite.config.ts       ← Vite + Tailwind v4
│   │
│   ├── bloom-ui/           ← Shared UI library (legacy, migrating)
│   └── docker-hub/         ← Docker deployment configs
│
├── turbo.json
└── package.json
```

> **2-package approach**: `bloom-app` chứa app code + shadcn primitives. `bloom-ui` hiện đang là legacy (Mantine-based) và sẽ dần được chuyển sang. Có thể thêm packages trong tương lai (ví dụ: `bloom-charts`, `bloom-shared`).

### Framework & Libraries chính

| Category | Library | Vai trò |
|----------|---------|---------|
| **UI Framework** | React 18 | Component-based UI |
| **CSS Framework** | Tailwind CSS v4 | Utility-first CSS (via `@tailwindcss/vite` plugin) |
| **UI Primitives** | shadcn/ui (Radix + CVA) | Headless accessible components với variant system |
| **Build Tool** | Vite 6 | Dev server + bundler |
| **Routing** | React Router v7 | Client-side routing, data router (useBlocker support) |
| **Data Fetching** | TanStack React Query v5 | Server state management, caching |
| **Data Tables** | TanStack Table v8 | Headless table logic (sort, filter, paginate) |
| **State Management** | Zustand 5 | Client state (auth, project, permission) |
| **Forms** | React Hook Form 7 | Form state management |
| **Form Validation** | Zod 3 + @hookform/resolvers | Schema-based validation |
| **HTTP Client** | Axios 1.7 | API calls (withCredentials for session cookies) |
| **Charts** | Recharts 2.15 | Data visualization |
| **Icons** | Lucide React | Icon set |
| **i18n** | i18next + react-i18next | Internationalization (vi + en) |
| **Toast** | Sonner | Toast notifications |
| **Cookies** | js-cookie | Client-side cookie management |

### UI Architecture (Builtiful-inspired)

| Pattern | Builtiful (PocketBase) | Kactus-Bloom (FastAPI) |
|---------|----------------------|----------------------|
| Schema source | `schema.go` → codegen → `blueprints.ts` | Hand-written TS types + Pydantic models |
| Form resolver | Auto from blueprint | Explicit zod schema |
| Field dispatch | `<Field />` auto from blueprint type | Caller picks primitive explicitly |
| Error bridge | `ClientResponseError` → `form.setError` | `AxiosError` + `ResponseModel` → `form.setError` |
| API client | PB SDK (`pb.collection(x).getList()`) | Axios (`apiClient.get('/api/x')`) |
| Data view columns | Auto from blueprint + override | Hand-write full `ViewSchema` |
| Layout | `EntityPage` 3-region | `EntityPage` 3-region (ported 1:1) |
| Module system | `defineAppModule` + auto-routing | `defineAppModule` + auto-routing (ported 1:1) |
| i18n | i18next + per-module locales | i18next + per-module locales (ported 1:1) |

### Path Aliases (TS, in `bloom-app/`)

- `@/...` resolves to `./src/*` (app root — `@/components/ui/...`, `@/lib/...`)
- `@modules/...` resolves to `./src/modules/*`

### Testing

| Library | Vai trò |
|---------|---------|
| Vitest 2.1 | Test framework (Vite-native) |
| @testing-library/react | React component testing |
| @testing-library/jest-dom | DOM assertion matchers |

### DevOps & Tooling

| Tool | Vai trò |
|------|---------|
| ESLint 9 | JavaScript/TypeScript linting |
| Prettier 3.4 | Code formatting |
| Husky 9 | Git hooks |
| lint-staged | Pre-commit lint |
| Docker + Docker Compose | Container deployment |

---

## Database Architecture

```
┌───────────────────────────────────────────────────┐
│                   OLTP (PostgreSQL)                │
│  ─ Users, Sessions, Projects, ProjectMembers      │
│  ─ Managed via Alembic migrations                 │
│  ─ Async access via asyncpg + SQLAlchemy          │
└───────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────┐
│                  OLAP (DuckDB)                     │
│  ─ Gold prices, Stock OHLCV, Financial reports    │
│  ─ Company overviews, Stock listings              │
│  ─ Embedded database (file-based)                 │
│  ─ Upsert/append strategies                       │
└───────────────────────────────────────────────────┘
```

## Ports & Services

| Service | Port | Mô tả |
|---------|------|-------|
| kactus-fin | 17600 | Main API server (internal) |
| kactus-fin-gateway | 17601 | Public API gateway |
| bloom-app | 17630 | Frontend dev server |
