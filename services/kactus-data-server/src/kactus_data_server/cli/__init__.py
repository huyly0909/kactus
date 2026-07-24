"""kactus-data-server CLI — server management.

No ``db`` subcommand on purpose: this service shares kactus-fin's database and
its single Alembic head. Migrations are run with ``manage.py fin db upgrade``.
"""

from kactus_common.cli import AsyncTyper

cli = AsyncTyper(help="Kactus Data Server — data plane (ETL, DuckDB, scheduler)")


def _add_subcommands():
    from kactus_data_server.cli import server  # noqa: F401


_add_subcommands()
