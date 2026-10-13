"""ContextVar-based current user / project tracking.

The session auth dependency sets the current user ID and selected project ID
after authentication. ``AuditMixin`` reads the user via ``get_current_user_id``
to auto-populate ``created_by`` / ``updated_by``; ``ProjectScopedMixin`` reads
the project via ``get_current_project_id`` to auto-populate ``project_id`` and
to scope SELECTs to the selected project.
"""

from __future__ import annotations

from contextvars import ContextVar

_current_user_id: ContextVar[int | None] = ContextVar("_current_user_id", default=None)
_current_project_id: ContextVar[int | None] = ContextVar(
    "_current_project_id", default=None
)


def get_current_user_id() -> int | None:
    """Read the current user ID from the request-scoped ContextVar."""
    return _current_user_id.get()


def set_current_user_id(user_id: int) -> None:
    """Set the current user ID (called by the auth dependency)."""
    _current_user_id.set(user_id)


def get_current_project_id() -> int | None:
    """Read the currently selected project ID from the request-scoped ContextVar."""
    return _current_project_id.get()


def set_current_project_id(project_id: int | None) -> None:
    """Set the selected project ID (called by the auth dependency).

    Always call this — including with ``None`` — so a request without a project
    cookie cannot inherit a previous request's project on the same worker.
    """
    _current_project_id.set(project_id)
