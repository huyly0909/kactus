"""Fire-and-forget audit writer.

``audit(...)`` returns instantly: it snapshots the current user/project from the
request ContextVars *synchronously*, then spawns a detached task that writes the
row on its own short-lived session. The request-scoped session injected by
``@provide_session`` is committed and closed the moment the endpoint returns, so
the writer must never touch it — it opens a brand-new one from ``get_db()``.

An audit write failing must never surface to the user, so every exception in the
writer is swallowed into a ``loguru.warning``.

TODO(audit): @audited decorator, request_id/ip via middleware, before/after
diffs in meta, and a GET /api/audit-logs read API.
"""

from __future__ import annotations

import asyncio

from kactus_common.database.oltp.session import get_db
from kactus_common.user.context import get_current_project_id, get_current_user_id
from loguru import logger

from .const import AuditOutcome
from .model import AuditLog

# Keep strong refs to in-flight tasks so they are not garbage-collected mid-write.
_pending: set[asyncio.Task] = set()


async def _write(entry: dict) -> None:
    try:
        async with get_db().get_session() as session:
            session.add(AuditLog(**entry))
            # get_session() commits on clean exit.
    except Exception as exc:  # noqa: BLE001 — audit must never bubble to the caller
        logger.warning(f"audit write failed action={entry.get('action')}: {exc}")


def audit(
    action: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    *,
    outcome: str = AuditOutcome.SUCCESS,
    meta: dict | None = None,
) -> None:
    """Record a user action. Fire-and-forget — never awaited, never raises.

    Context (user/project) is snapshotted now, before the task is spawned, so the
    written row does not depend on request-context lifetime.
    """
    entry = {
        "user_id": get_current_user_id(),
        "project_id": get_current_project_id(),
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outcome": str(outcome),
        "meta": meta or {},
    }
    try:
        task = asyncio.create_task(_write(entry))
    except RuntimeError:
        # No running event loop (sync context / CLI / some tests).
        logger.warning(f"audit skipped (no running loop) action={action}")
        return
    _pending.add(task)
    task.add_done_callback(_pending.discard)
