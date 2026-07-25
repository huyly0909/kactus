"""Application-level dependency injection.

Re-exports common utilities so kactus-fin modules import from one place.
"""

from kactus_common.database.oltp.session import get_db, provide_session
from kactus_common.user.auth import get_auth

__all__ = ["get_db", "get_auth", "provide_session"]
