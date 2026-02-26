"""ContextVar-based current user tracking.

The session auth dependency sets the current user ID after authentication.
``AuditMixin`` reads it via ``get_current_user_id`` to auto-populate
``created_by`` / ``updated_by`` on INSERT / UPDATE.
"""

from __future__ import annotations

from contextvars import ContextVar

_current_user_id: ContextVar[int | None] = ContextVar("_current_user_id", default=None)


def get_current_user_id() -> int | None:
    """Read the current user ID from the request-scoped ContextVar."""
    return _current_user_id.get()


def set_current_user_id(user_id: int) -> None:
    """Set the current user ID (called by the auth dependency)."""
    _current_user_id.set(user_id)
