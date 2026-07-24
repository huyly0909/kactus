"""Schema drift check / rebuild for the DuckDB (OLAP) tables.

DuckDB tables are created with ``CREATE TABLE IF NOT EXISTS``, so editing a
table definition has no effect on a database that already holds that table.
There is no OLAP migration tool — ``check`` reports the gap and ``recreate``
closes it by dropping and rebuilding. Recreating discards rows; re-run the
relevant crawl afterwards to refill.
"""

import typer
from kactus_data.config import DataSettings
from kactus_data.sources.registry import ALL_TABLES, TABLES_BY_NAME
from typer import Context, Option, Typer

cli = Typer()

_defaults = DataSettings()


@cli.callback()
def main(
    ctx: Context,
    db_path: str = Option(_defaults.db_path, help="Path to DuckDB database file"),
):
    """DuckDB schema inspection commands."""
    from kactus_data.storage.duckdb import DuckDBStorage

    ctx.obj = {"storage": DuckDBStorage(db_path)}


@cli.command()
def check(ctx: Context):
    """Report tables whose on-disk schema differs from their definition."""
    storage = ctx.obj["storage"]
    drifted = 0

    for table in ALL_TABLES:
        if not storage.client.table_exists(table.name):
            typer.secho(f"  {table.name}: not created yet", fg=typer.colors.BLUE)
            continue
        drift = storage.schema_drift(table)
        if not drift:
            typer.secho(f"  {table.name}: ok", fg=typer.colors.GREEN)
            continue
        drifted += 1
        typer.secho(f"  {table.name}:", fg=typer.colors.YELLOW)
        for line in drift:
            typer.echo(f"      {line}")

    if drifted:
        typer.secho(
            f"\n{drifted} table(s) drifted — run `schema recreate` to rebuild "
            "(this discards their rows).",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(1)
    typer.secho("\nAll tables match their definitions.", fg=typer.colors.GREEN)


@cli.command()
def recreate(
    ctx: Context,
    table_name: str = typer.Argument(
        None, help="Table to rebuild; omit to rebuild every drifted table"
    ),
    yes: bool = Option(False, "-y", "--yes", help="Skip the confirmation prompt"),
):
    """Drop and rebuild tables from their definitions. Destroys their rows."""
    storage = ctx.obj["storage"]

    if table_name:
        table = TABLES_BY_NAME.get(table_name)
        if table is None:
            known = ", ".join(sorted(TABLES_BY_NAME))
            typer.secho(
                f"Unknown table '{table_name}'. Known: {known}", fg=typer.colors.RED
            )
            raise typer.Exit(1)
        targets = [table]
    else:
        targets = [t for t in ALL_TABLES if storage.schema_drift(t)]

    if not targets:
        typer.secho("Nothing to recreate.", fg=typer.colors.GREEN)
        return

    typer.secho("Will DROP and rebuild (all rows lost):", fg=typer.colors.YELLOW)
    for t in targets:
        typer.echo(f"  - {t.name}")

    if not yes:
        typer.confirm("Proceed?", abort=True)

    for t in targets:
        storage.recreate_table(t)
        typer.secho(f"  recreated {t.name}", fg=typer.colors.GREEN)

    typer.secho(
        f"\nRebuilt {len(targets)} table(s). Re-run the matching crawl to refill.",
        fg=typer.colors.GREEN,
    )
