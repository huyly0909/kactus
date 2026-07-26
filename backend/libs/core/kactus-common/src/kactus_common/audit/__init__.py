"""Fire-and-forget audit trail of user actions.

``audit(...)`` snapshots the current user/project from ContextVars and writes an
:class:`AuditLog` row in a detached task on its own short-lived session, so it
never blocks or fails the request that triggered it.
"""

from .const import AuditOutcome
from .model import AuditLog
from .service import audit

__all__ = ["audit", "AuditLog", "AuditOutcome"]
