"""kactus-data CLI — ETL management commands."""

from kactus_common.cli import AsyncTyper

cli = AsyncTyper(help="Kactus Data — ETL pipelines & backups")


def _add_subcommands():
    from kactus_data.cli import backup, sync  # noqa: F401

    cli.add_typer(backup.cli, name="backup", help="DuckDB backup / export")


_add_subcommands()
