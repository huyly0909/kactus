"""Backup / export commands for DuckDB tables."""

import typer

from typer import Context, Option, Typer

cli = Typer()


@cli.callback()
def main(
    ctx: Context,
    db_path: str = Option("kactus.duckdb", help="Path to DuckDB database file"),
):
    """DuckDB backup and export commands."""
    from kactus_data.storage.duckdb import DuckDBStorage

    ctx.obj = {"storage": DuckDBStorage(db_path)}


@cli.command()
def table(
    ctx: Context,
    table_name: str = typer.Argument(help="Table to export"),
    output: str = Option("./backups", "-o", "--output", help="Output directory"),
    format: str = Option("parquet", "-f", "--format", help="Export format: parquet or csv"),
):
    """Export a single table to a file."""
    storage = ctx.obj["storage"]

    if not storage.client.table_exists(table_name):
        typer.secho(f"Table '{table_name}' not found", fg=typer.colors.RED)
        raise typer.Exit(1)

    path = storage.export_table(table_name, output, format)
    typer.secho(f"Exported → {path}", fg=typer.colors.GREEN)


@cli.command(name="all")
def all_tables(
    ctx: Context,
    output: str = Option("./backups", "-o", "--output", help="Output directory"),
    format: str = Option("parquet", "-f", "--format", help="Export format: parquet or csv"),
):
    """Export all tables to individual files."""
    storage = ctx.obj["storage"]
    paths = storage.export_database(output, format)

    if not paths:
        typer.secho("No tables found to export", fg=typer.colors.YELLOW)
        return

    for path in paths:
        typer.echo(f"  → {path}")
    typer.secho(f"\nExported {len(paths)} tables", fg=typer.colors.GREEN)


@cli.command(name="list")
def list_tables(ctx: Context):
    """List all tables in the database."""
    storage = ctx.obj["storage"]
    tables = storage.list_tables()

    if not tables:
        typer.secho("No tables found", fg=typer.colors.YELLOW)
        return

    for name in tables:
        typer.echo(f"  • {name}")
    typer.secho(f"\n{len(tables)} tables", fg=typer.colors.GREEN)
