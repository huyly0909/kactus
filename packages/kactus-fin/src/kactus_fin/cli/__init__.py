"""kactus-fin CLI — server management and database commands."""

import typer

from kactus_common.cli import AsyncTyper

cli = AsyncTyper(help="Kactus Fin — main API server")


def _add_subcommands():
    from kactus_fin.cli import db, server  # noqa: F401

    cli.add_typer(db.cli, name="db", help="Database migrations (Alembic)")


_add_subcommands()
