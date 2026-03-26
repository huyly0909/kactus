# Security Audit & Bug Report

**Date:** 2026-03-26
**Scope:** kactus backend (kactus-common, kactus-fin, kactus-data)

---

## CRITICAL — FIXED

### 1. SQL Injection in DuckDB Service Queries — FIXED

All DuckDB queries in the finance/company/stock services were using f-string interpolation with user-supplied parameters, enabling SQL injection attacks.

**Fix applied:** Added `params` argument to `DatabaseClient.execute()` and `DuckDBStorage.query()`, then converted all 4 service files to use `?` placeholders with parameterized queries.

**Files changed:**
- `packages/kactus-common/src/kactus_common/database/duckdb/client.py` — `execute()` now accepts `params: list | None`
- `packages/kactus-data/src/kactus_data/storage/duckdb.py` — `query()` now accepts `params: list | None`
- `packages/kactus-fin/src/kactus_fin/company/service.py` — parameterized `symbol`
- `packages/kactus-fin/src/kactus_fin/stock/service.py` — parameterized `symbol`
- `packages/kactus-fin/src/kactus_fin/finance/service.py` — parameterized `symbol` and `report_type`

**Tests:** `test_company_service.py::test_sql_injection_is_prevented`, `test_finance_service.py` filter tests verify params.

### 2. Wide-Open CORS Configuration — FIXED

`allow_origins=["*"]` with `allow_credentials=True` was a security anti-pattern.

**Fix applied:** Added `cors_allowed_origins: list[str]` to `CommonSettings` (default: `["http://localhost:17630"]`). CORS middleware now reads from settings instead of wildcard. Configurable per environment via `KACTUS_CORS_ALLOWED_ORIGINS`.

**Files changed:**
- `packages/kactus-common/src/kactus_common/config.py` — added `cors_allowed_origins`
- `packages/kactus-fin/src/kactus_fin/app.py` — `allow_origins=settings.cors_allowed_origins`

**Tests:** `test_app.py::TestCORSConfiguration` (3 tests).

---

## LOW — FIXED

### 6. Missing Security Headers — FIXED

**Fix applied:** Added `SecurityHeadersMiddleware` to kactus-fin app that sets:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Strict-Transport-Security` (when `session_cookie_secure=True`, i.e. prod)

**Files changed:** `packages/kactus-fin/src/kactus_fin/app.py`

**Tests:** `test_app.py::TestSecurityHeaders` (4 tests).

### 7. DuckDB Client Manual SQL Construction — FIXED

DELETE queries in `_upsert_table_data` and `_insert_overwrite_table_data` were using manual string interpolation for values.

**Fix applied:** Converted to parameterized queries with `?` placeholders. Added `_to_python_type()` helper to convert numpy types to native Python types for DuckDB parameter binding.

Also fixed:
- Replaced `import logging` with `from loguru import logger` (per project conventions)
- Replaced bare `except:` with `except Exception:` in `table_exists()`

**Files changed:** `packages/kactus-common/src/kactus_common/database/duckdb/client.py`

---

## MEDIUM — OPEN

### 3. No Password Validation on Admin Create User

**File:** `packages/kactus-fin/src/kactus_fin/admin/api.py`

`AdminCreateUserRequest` accepts any string as password with no minimum length or complexity requirements.

**Status:** TODO — not blocking for test stage.

### 4. Race Condition in Project Creation (TOCTOU)

**File:** `packages/kactus-common/src/kactus_common/project/service.py` lines 31-56

The code checks for duplicates then creates, but two concurrent requests could both pass the check. The DB unique constraint catches this, but the resulting `IntegrityError` is unhandled and returns a 500 instead of a clean 409.

**Fix:** Catch `IntegrityError` after commit:
```python
from sqlalchemy.exc import IntegrityError

try:
    await session.commit()
except IntegrityError:
    await session.rollback()
    raise ConflictError(f"Project with code '{code}' already exists")
```

### 5. No Rate Limiting on Login

**File:** `packages/kactus-fin/src/kactus_fin/auth/api.py`

The login endpoint has no rate limiting, allowing unlimited password attempts (brute-force attacks).

**Fix:** Add `slowapi` middleware or implement a per-IP/per-email attempt counter.
