"""hash user session ids

``user_sessions.session_id`` held the raw cookie token, and auth looked it up
by the raw cookie value — so anyone who could read the table (a dump, a backup,
a replica) could copy a value into ``kactus_session_id`` and be logged in as
that user, for up to a year on remember-me sessions. The column now stores the
SHA-256 of the token as ``session_hash``; the raw token lives only in the
cookie.

Existing rows hold raw tokens that cannot be kept, so they are deleted:
deploying this logs every user out once.

Revision ID: 58672e43b957
Revises: c1d2e3f4a5b6
Create Date: 2026-10-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "58672e43b957"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DELETE FROM user_sessions")

    op.drop_index("ix_user_sessions_user_id_session_id", table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_session_id"), table_name="user_sessions")
    op.alter_column("user_sessions", "session_id", new_column_name="session_hash")
    op.create_index(
        op.f("ix_user_sessions_session_hash"),
        "user_sessions",
        ["session_hash"],
        unique=True,
    )
    op.create_index(
        "ix_user_sessions_user_id_session_hash",
        "user_sessions",
        ["user_id", "session_hash"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # A hash cannot be turned back into the token the old code looks up.
    op.execute("DELETE FROM user_sessions")

    op.drop_index("ix_user_sessions_user_id_session_hash", table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_session_hash"), table_name="user_sessions")
    op.alter_column("user_sessions", "session_hash", new_column_name="session_id")
    op.create_index(
        op.f("ix_user_sessions_session_id"),
        "user_sessions",
        ["session_id"],
        unique=True,
    )
    op.create_index(
        "ix_user_sessions_user_id_session_id",
        "user_sessions",
        ["user_id", "session_id"],
        unique=False,
    )
