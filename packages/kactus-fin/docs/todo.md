# TODO — Deferred Items

## Session Cleanup Job
- [ ] Add a periodic task to clean up expired sessions: `DELETE FROM user_sessions WHERE expires_at < now()`
- Consider: cron job, Celery beat, or FastAPI background task
- Low priority — expired sessions are already rejected on read, this is just DB hygiene

## User Roles & Permissions
- [ ] Add project-based roles (not simple role field)
- [ ] Add author tracking
- [ ] Design RBAC model for multi-project access

## Password Policies
- [ ] Password complexity enforcement (min length, special chars, etc.)
- [ ] Password expiry / rotation
- [ ] Account lockout after N failed login attempts
