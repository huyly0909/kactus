"""One-off timezone backfill for the DuckDB (OLAP) tables.

Brings pre-existing rows in line with the UTC convention:

1. **``event_dt`` (idempotent).** Adds the reserved ``event_dt`` column where it
   is missing and (re)computes it from each row's native Vietnam-local value —
   ``(native AT TIME ZONE 'Asia/Ho_Chi_Minh') AT TIME ZONE 'UTC'``. Because it is
   derived purely from the untouched native column, re-running is safe.

2. **Audit stamps (NOT idempotent, opt-in).** ``crawled_at`` / ``synced_at`` were
   written in the server's local time before this change. ``--shift-audit`` moves
   them by ``--server-offset`` hours to UTC. Running it twice double-shifts, so it
   is gated behind ``--confirm`` and off by default (a fresh crawl overwrites
   these anyway).

Run inside the data plane — DuckDB allows a single writer::

    python manage.py data tz backfill --confirm
    python manage.py data tz backfill --confirm --shift-audit --server-offset 7
"""

import typer
from kactus_data.config import DataSettings
from typer import Context, Option

cli = typer.Typer()

_defaults = DataSettings()

#: table → SQL expression yielding the native Vietnam-local instant that
#: ``event_dt`` is derived from. ``TRY_CAST`` leaves unparseable strings NULL.
_EVENT_DT_SOURCES: dict[str, str] = {
    "stock_ohlcv": "time",
    "gold_price_history": "CAST(date AS TIMESTAMP)",
    "stock_news": "TRY_CAST(published_at AS TIMESTAMP)",
    "stock_events": "TRY_CAST(event_date AS TIMESTAMP)",
    "stock_foreign_trade": "TRY_CAST(trade_date AS TIMESTAMP)",
}

#: table → audit timestamp columns written in server-local time historically.
_AUDIT_COLS: dict[str, list[str]] = {
    "gold_price_board": ["crawled_at"],
    "stock_price_board": ["crawled_at"],
    "stock_news": ["crawled_at"],
    "stock_events": ["crawled_at"],
    "stock_foreign_trade": ["crawled_at"],
    "stock_ratios": ["crawled_at"],
    "stock_listing": ["synced_at"],
    "stock_finance": ["synced_at"],
    "stock_company": ["synced_at"],
}


@cli.callback()
def main(
    ctx: Context,
    db_path: str = Option(_defaults.db_path, help="Path to DuckDB database file"),
):
    """DuckDB timezone backfill commands."""
    from kactus_data.storage.duckdb import DuckDBStorage

    ctx.obj = {"storage": DuckDBStorage(db_path)}


@cli.command()
def backfill(
    ctx: Context,
    confirm: bool = Option(
        False, "--confirm", help="Actually run (otherwise a dry-run listing)"
    ),
    shift_audit: bool = Option(
        False, "--shift-audit", help="Also shift server-local audit stamps to UTC"
    ),
    server_offset: int = Option(
        7, "--server-offset", help="Hours to subtract from audit stamps (VN=7, UTC=0)"
    ),
):
    """Populate ``event_dt`` from native columns; optionally UTC-shift audit stamps."""
    storage = ctx.obj["storage"]
    client = storage.client

    if not confirm:
        typer.secho("Dry run — pass --confirm to apply. Would:", fg=typer.colors.YELLOW)
        for table in _EVENT_DT_SOURCES:
            typer.echo(f"  - {table}: add + recompute event_dt (idempotent)")
        if shift_audit:
            for table, cols in _AUDIT_COLS.items():
                typer.echo(
                    f"  - {table}: {', '.join(cols)} -= {server_offset}h (NOT idempotent)"
                )
        return

    # 1. event_dt — idempotent (derived from the untouched native column).
    for table, expr in _EVENT_DT_SOURCES.items():
        if not client.table_exists(table):
            typer.secho(f"  {table}: not created yet, skipping", fg=typer.colors.BLUE)
            continue
        client.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS event_dt TIMESTAMP"
        )
        client.execute(
            f"UPDATE {table} SET event_dt = "  # noqa: S608 - table names are from a fixed allow-list
            f"(({expr}) AT TIME ZONE 'Asia/Ho_Chi_Minh') AT TIME ZONE 'UTC'"
        )
        typer.secho(f"  {table}: event_dt recomputed", fg=typer.colors.GREEN)

    # 2. audit stamps — one-off, not idempotent.
    if shift_audit and server_offset:
        for table, cols in _AUDIT_COLS.items():
            if not client.table_exists(table):
                continue
            for col in cols:
                client.execute(
                    f"UPDATE {table} SET {col} = {col} - INTERVAL {server_offset} HOUR "  # noqa: S608
                    f"WHERE {col} IS NOT NULL"
                )
            typer.secho(
                f"  {table}: {', '.join(cols)} shifted -{server_offset}h",
                fg=typer.colors.GREEN,
            )

    typer.secho("\nBackfill complete.", fg=typer.colors.GREEN)
