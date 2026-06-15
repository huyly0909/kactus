# Cách hoạt động & Workflow

## Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│                       FRONTEND (kactus-bloom)                   │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   bloom-app   │◄──│   bloom-ui    │    │  docker-hub  │       │
│  │  (Vite + React)│   │  (Components, │    │  (Deployment) │      │
│  │  Pages, Router │   │   Hooks,      │    └──────────────┘      │
│  │  Layouts       │   │   Services,   │                          │
│  └───────┬────────┘   │   Stores)     │                          │
│          │            └──────────────┘                           │
│          │  Axios (withCredentials)                               │
└──────────┼───────────────────────────────────────────────────────┘
           │
           │  HTTP (REST API)                    Session Cookies
           │  Port 17600                         (httpOnly)
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                       BACKEND (kactus)                           │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐          │
│  │  kactus-fin   │  │ kactus-fin-  │  │  kactus-data  │          │
│  │  (Main API)   │  │  gateway     │  │  (ETL/Data)   │          │
│  │  Port 17600   │  │  Port 17601  │  │               │          │
│  └───────┬───────┘  └──────┬───────┘  └───────┬───────┘          │
│          │                 │                  │                   │
│          └────────────┬────┘                  │                   │
│                       │                       │                   │
│              ┌────────┴────────┐              │                   │
│              │  kactus-common  │◄─────────────┘                   │
│              │  (Shared infra) │                                  │
│              └────────┬────────┘                                  │
│                       │                                           │
│          ┌────────────┼────────────┐                              │
│          ▼            ▼            ▼                              │
│     PostgreSQL     DuckDB      Casbin                            │
│     (OLTP)        (OLAP)      (RBAC)                             │
└──────────────────────────────────────────────────────────────────┘
```

---

## Backend Package Architecture

### Dependency Chain

```
kactus-fin  ──────┐
kactus-fin-gateway ──┤──► kactus-common
kactus-data  ─────┘

kactus-fin ──► kactus-data ──► kactus-common
```

### Settings Inheritance

```
BaseKactusSettings          ← app_env, debug, log_level
  └── CommonSettings        ← database_url, db_path, encryption_key
      ├── DataSettings      ← data_source (kactus-data)
      │   └── fin Settings  ← host, port, … (loads .env)
      └── gw Settings       ← host, port, … (loads .env)
```

Mỗi package cuối cùng (kactus-fin, kactus-fin-gateway) load `.env` file riêng, và tất cả settings được thừa kế ngược lên qua chain. Module dùng chung (kactus-common) access settings qua **settings registry** — không import trực tiếp từ downstream package.

---

## Authentication Workflow

### Login Flow

```
Client (Browser)                  Backend (kactus-fin)
     │                                  │
     │  POST /api/auth/login            │
     │  { email, password, remember }   │
     ├─────────────────────────────────►│
     │                                  │  1. Tìm user theo email
     │                                  │  2. Verify bcrypt password hash
     │                                  │  3. Tạo session record trong DB
     │                                  │  4. Set-Cookie: kactus_session_id
     │◄─────────────────────────────────┤     (httpOnly, secure, samesite=lax)
     │  Response: { user: UserInfo }    │
     │                                  │
```

### Session Authentication (mỗi request)

```
Client                             Backend
  │                                  │
  │  GET /api/projects               │
  │  Cookie: kactus_session_id=xxx   │
  ├─────────────────────────────────►│
  │                                  │  1. Đọc session cookie
  │                                  │  2. Tìm UserSession trong DB
  │                                  │  3. Load User từ session
  │                                  │  4. Set request.state.user
  │                                  │  5. Set request.state.project_id
  │                                  │     (từ kactus_project_id cookie)
  │                                  │  6. Set ContextVar cho AuditMixin
  │◄─────────────────────────────────┤
  │  Response data                   │
```

### Key Points
- **Session-based auth** (không phải JWT) — session ID lưu trong httpOnly cookie
- Cookie `kactus_session_id` — httpOnly, secure (prod), samesite=lax
- Cookie `kactus_project_id` — client-managed, dùng js-cookie, lưu project đang chọn
- Session expiry: 7 ngày (default), 1 năm (remember me)

---

## Authorization (RBAC) Workflow

### Casbin Policy Model

```
[request_definition]
r = sub, obj, act          ← role, permission, action

[matchers]
m = r.sub == p.sub && r.obj == p.obj && r.act == p.act
```

### Permission Hierarchy

```
manage  →  cũng được phép write và read
write   →  cũng được phép read
read    →  chỉ được read
```

### Flow khi gọi API có @permission decorator

```
1. Request đến endpoint (VD: PUT /api/projects/{id})
2. Session auth middleware → set request.state.user
3. @permission(ProjectPermission.project, PermissionAct.write) kiểm tra:
   a. Nếu user.is_superuser → bypass, cho phép
   b. Lấy project_id từ request.state.project_id (cookie)
   c. Tìm role của user trong project (ProjectMember table)
   d. Dùng CasbinService.enforce(role, permission, act) kiểm tra
   e. Nếu không đủ quyền → raise PermissionDeniedError
4. Endpoint handler chạy nếu pass authorization
```

### Role-Permission Registration (startup)

```
1. Mỗi feature khai báo KactusApp với role_permissions
2. AppManager.register() thu thập tất cả feature apps
3. AppManager.init_fastapi() → _init_authorization()
4. CasbinService load policies từ aggregated role_permissions
5. Permission hierarchy được expand tự động
```

---

## Data Pipeline Workflow (kactus-data)

### Sync Pipeline Pattern

```
Data Source (API/Scraper)
     │
     │  1. FETCH — source.sync(start_date, end_date, code)
     │     → SyncDataResponse { success, data, error }
     ▼
Transform (optional)
     │
     │  2. TRANSFORM — raw dict → pd.DataFrame
     │     Reorder columns theo table schema
     ▼
DuckDB Storage
     │
     │  3. STORE — storage.store(table, df, strategy)
     │     Strategy: UPSERT | APPEND | REPLACE
     ▼
SyncResult { rows_fetched, rows_stored, duration_ms }
```

### Các Data Sources hiện có

| Source Class | Nguồn dữ liệu | Dữ liệu |
|-------------|----------------|----------|
| `MihongGoldSource` | mihong.vn API | Giá vàng trong nước (SJC, etc.) |
| `VnstockOHLCVSource` | vnstock (KBS) | Candlestick OHLCV (1m → 1M) |
| `VnstockListingSource` | vnstock (KBS) | Danh sách mã cổ phiếu niêm yết |
| `VnstockFinanceSource` | vnstock (KBS) | Báo cáo tài chính (income, balance, cash flow, ratio) |
| `VnstockCompanySource` | vnstock (VCI) | Thông tin tổng quan công ty |

### DuckDB Storage Strategies

| Strategy | Mô tả |
|----------|-------|
| UPSERT | Insert hoặc update nếu trùng key |
| APPEND | Chỉ insert thêm |
| REPLACE | Xóa toàn bộ rồi insert lại |

---

## Frontend Application Workflow

### App Initialization

```
main.tsx
  │
  ├── QueryClientProvider (TanStack Query — staleTime: 5 min)
  ├── MantineProvider (custom theme)
  ├── Notifications (top-right)
  └── App
       └── BrowserRouter
            └── AppRouter (Routes)
```

### Routing & Guards

```
Routes
  ├── /login                    ← AuthLayout (public)
  │
  ├── AuthGuard (kiểm tra session)
  │   │
  │   ├── AdminGuard (kiểm tra is_superuser)
  │   │   └── AdminLayout
  │   │       ├── /admin/users
  │   │       ├── /admin/projects
  │   │       └── /admin/authorization
  │   │
  │   └── MainLayout
  │       ├── /select-project   ← chọn project
  │       │
  │       └── ProjectGuard (kiểm tra đã chọn project)
  │           ├── /welcome
  │           └── /dashboard
  │
  ├── / → redirect /welcome
  └── * → NotFound
```

### State Management (Zustand Stores)

| Store | Dữ liệu | Mô tả |
|-------|---------|-------|
| `useAuthStore` | user, isAuthenticated, isLoading | Trạng thái auth (session cookie managed by server) |
| `useProjectStore` | currentProject, isLoading | Project đang chọn (persist qua cookie `kactus_project_id`) |
| `usePermissionStore` | permissions[], role, isSuperuser | Permissions trong project hiện tại |
| `uiStore` | UI state | Trạng thái giao diện |

### API Communication Pattern

```
Component
  │
  │  useAuth() / useProject() / usePermission()
  │  (Custom hooks wrapping TanStack Query)
  ▼
Service Layer (authService, projectService, adminService)
  │
  │  apiClient (Axios instance)
  │  withCredentials: true → browser auto-sends session cookie
  │  401 interceptor → redirect to /login
  ▼
Backend API (/api/...)
  │
  │  ResponseModel<T> wrapper
  │  { code: "0", msg: "success", data: T }
  ▼
Response
```

---

## Feature App Pattern (Backend)

Mỗi feature module trong backend tuân theo pattern thống nhất:

### 1. Khai báo KactusApp (`app.py`)

```python
from kactus_common.app_registry import KactusApp

project_app = KactusApp(
    name="project",
    public_routes=[router],       # Không cần auth
    session_routes=[router],      # Cần session auth
    superuser_routes=[router],    # Cần superuser
    permissions=[...],            # Permission codes
    role_permissions={...},       # Default role → permission mapping
)
```

### 2. Router (`api.py`)

```python
from kactus_common.router import KactusAPIRouter

router = KactusAPIRouter(prefix="/api/projects", tags=["projects"])

@router.get("")
@provide_session  # Auto-inject AsyncSession
async def list_projects(request: Request, session: AsyncSession):
    ...
```

### 3. `KactusAPIRouter` auto-wraps

Response tự động wrap trong `ResponseModel<T>`:
```json
{
  "code": "0",
  "msg": "success",
  "data": { /* actual response */ }
}
```

### 4. Đăng ký trong `app.py` chính

```python
app_manager = AppManager()
app_manager.register(auth_app)
app_manager.register(project_app)
app_manager.set_auth_dependencies(...)
# init_fastapi() → wire routes, middleware, casbin policies
```

---

## Deployment Workflow

```
Development:
  Backend:   python manage.py fin dev          # uvicorn hot-reload
  Frontend:  pnpm dev --filter bloom-app       # vite hot-reload

Docker (dev/stag/prod):
  cd packages/docker-hub/{env}
  docker compose up -d

  # Migrations
  docker compose exec kactus-fin python manage.py fin db upgrade

CLI Commands:
  python manage.py fin dev|stag|prod           # Run kactus-fin
  python manage.py fin-gw dev|stag|prod        # Run gateway
  python manage.py fin db migrate -m "..."     # Create migration
  python manage.py fin db upgrade              # Apply migrations
  python manage.py fin db downgrade <rev>      # Rollback migration
  python manage.py data ...                    # Data ETL commands
```

---

## Exception Handling

Backend có hệ thống exception thống nhất:

| Exception | HTTP Code | Khi nào |
|-----------|-----------|---------|
| `InvalidArgumentError` | 400 | Argument không hợp lệ |
| `ValidationError` | 400 | Input validation fail |
| `AuthenticationError` | 401 | Chưa login / session expired |
| `PermissionDeniedError` | 403 | Không đủ quyền |
| `NotFoundError` | 404 | Resource không tìm thấy |
| `ConflictError` | 409 | Trùng lặp (VD: project code) |
| `RateLimitError` | 429 | Vượt quá rate limit |
| `DatabaseError` | 500 | Lỗi database |
| `InternalError` | 500 | Lỗi server không xác định |
| `DataSourceError` | 502 | Lỗi từ data source bên ngoài |
| `ExternalServiceError` | 502 | Lỗi gọi API bên ngoài |
| `TimeoutError` | 504 | Timeout |

Tất cả response lỗi có format thống nhất:
```json
{
  "code": "PERMISSION_DENIED",
  "title": "Permission Denied",
  "message": "Insufficient permissions",
  "tip": "...",        // optional
  "data": { ... }      // optional context
}
```
