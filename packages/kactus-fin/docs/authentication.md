# Authentication Flow — Kactus Fin

> Session-based authentication using httpOnly cookies.

## Overview

Kactus uses **session-based authentication** (not JWT). On login, the server creates a session row in the database and sets a `kactus_session_id` httpOnly cookie. The browser sends this cookie automatically on every request.

## Login Flow

```
┌──────────┐     POST /api/auth/login         ┌──────────┐       ┌──────────┐
│          │  ─── {email, password, remember} ──▶          │       │          │
│  Browser │                                   │  Server  │──────▶│ Database │
│          │  ◀── Set-Cookie: kactus_session_id │          │       │          │
└──────────┘     (httpOnly, max-age=7d)        └──────────┘       └──────────┘
```

### Steps

1. User enters email + password on login page
2. Frontend sends `POST /api/auth/login` with `{ email, password, remember }`
3. Server looks up user by email in `users` table
4. Server verifies password using bcrypt (`verify_password(input, hash)`)
5. Server creates a `UserSession` row:
   - `session_id` = UUID v4
   - `expires_at` = `now + 7 days` (or `now + 1 year` if `remember=True`)
6. Server sets cookie: `kactus_session_id=<uuid>`
   - `httpOnly=True` — JavaScript cannot read it (XSS protection)
   - `SameSite=Lax` — sent with same-site and top-level navigations
   - `Secure=True` in production (HTTPS only)
   - `max-age` = same as `expires_at` duration
7. Server returns `LoginResponse` with user info
8. Frontend redirects to `/welcome`

## Authenticated Request Flow

```
┌──────────┐     GET /api/auth/me              ┌──────────┐       ┌──────────┐
│          │  ── Cookie: kactus_session_id ────▶│          │       │          │
│  Browser │                                   │  Server  │──────▶│ Database │
│          │  ◀── { user: { id, email, ... } }  │          │       │          │
└──────────┘                                   └──────────┘       └──────────┘
```

### Steps

1. Browser automatically includes `kactus_session_id` cookie
2. Auth middleware reads `session_id` from cookie
3. Looks up `UserSession` row in database
4. Checks `if session.expires_at < now()`:
   - **Expired** → delete session row, return HTTP 401
   - **Valid** → load associated `User`, continue
5. The `User` object is available via FastAPI's `Depends(get_current_user)`

## Logout Flow

1. Frontend sends `POST /api/auth/logout`
2. Server reads `session_id` from cookie
3. Server deletes `UserSession` row from database
4. Server clears the cookie (set `max-age=0`)
5. Frontend redirects to `/login`

## Session Expiration

Sessions expire through **two independent mechanisms**:

| Mechanism | Where | How |
|-----------|-------|-----|
| **Server-side** | `user_sessions.expires_at` column | Auth middleware checks on every request. If expired → 401 + delete row |
| **Client-side** | Cookie `max-age` attribute | Browser auto-deletes cookie when it expires |

Even if someone tampers with the cookie expiry, the server-side check is the **real enforcement**.

### Expiry durations

| Type | Duration | When |
|------|----------|------|
| Normal session | 7 days | `remember=False` (default) |
| Remember me | 1 year | `remember=True` |

## Password Storage

Passwords are hashed using **bcrypt** (one-way hash, not reversible):

```python
# On registration / password change
password_hash = hash_password("user_password")  # bcrypt hash

# On login
is_valid = verify_password("user_input", user.password_hash)
```

> **Why not Fernet?** Fernet is reversible encryption — if the key leaks, all passwords are compromised. Bcrypt is a one-way hash; even with full database access, passwords cannot be recovered.

## Cookie Security Flags

| Flag | Value | Purpose |
|------|-------|---------|
| `httpOnly` | `True` | JavaScript cannot access the cookie (prevents XSS attacks) |
| `SameSite` | `Lax` | Cookie sent with same-site requests + top-level navigations |
| `Secure` | `True` in prod | Cookie only sent over HTTPS (prevents MITM attacks) |
| `max-age` | 7d or 1y | Browser auto-deletes when expired |

## Swagger UI

Swagger UI works natively with session cookies:

1. Open Swagger at `http://localhost:17600/docs`
2. Call `POST /api/auth/login` with credentials via "Try it out"
3. The browser sets the httpOnly cookie automatically
4. All subsequent "Try it out" calls include the cookie
5. Call `GET /api/auth/me` to verify the session is active

## Database Tables

### `users`

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGINT (snowflake) | Primary key |
| `email` | VARCHAR | Unique |
| `username` | VARCHAR | Unique |
| `password_hash` | VARCHAR | bcrypt hash |
| `name` | VARCHAR | Display name |
| `status` | VARCHAR | `active` / `inactive` / `locked` |
| `last_login` | TIMESTAMP | Last successful login |
| `created_by` | BIGINT | Audit mixin |
| `updated_by` | BIGINT | Audit mixin |
| `create_time` | TIMESTAMP | Auto |
| `update_time` | TIMESTAMP | Auto |
| `deleted_timestamp` | BIGINT | Soft delete (0 = not deleted) |

### `user_sessions`

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGINT (snowflake) | Primary key |
| `user_id` | BIGINT | FK → users.id |
| `session_id` | VARCHAR | UUID v4, unique index |
| `expires_at` | TIMESTAMP | Server-side expiration |
| `is_remember` | BOOLEAN | Remember-me flag |
| `create_time` | TIMESTAMP | Auto |
| `update_time` | TIMESTAMP | Auto |

## Environment Variables

```bash
KACTUS_DATABASE_URL=postgresql://user:pass@localhost:5432/kactus
KACTUS_ENCRYPTION_KEY=<fernet-key>          # generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
KACTUS_SESSION_COOKIE_SECURE=false          # true in prod
```
