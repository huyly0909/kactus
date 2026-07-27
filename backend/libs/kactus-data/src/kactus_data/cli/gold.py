"""Gold backfill / sync CLI — run the sync-job handlers inline (local debug).

These commands execute the same ``GOLD_BACKFILL`` / ``GOLD_SYNC`` handlers the
data-plane dispatcher runs, but **inline** against a local DuckDB handle, with
progress printed to stdout. Handlers only touch DuckDB + the progress callback
(never Postgres), so this needs no database or running server — the in-app path
(superuser → queue) is where jobs are enqueued for real.

Examples::

    python manage.py data gold backfill --source sjc --from 2009-07-22 --to 2026-07-26
    python manage.py data gold backfill --source yahoo   # XAU, from its min to today
    python manage.py data gold backfill --source mihong  # 999, trailing 1 year
    python manage.py data gold sync                        # all sources, now
    python manage.py data gold sync --source mihong
"""

from __future__ import annotations

import asyncio
from datetime import date

import typer
from kactus_common.cli import AsyncTyper
from kactus_data.config import get_settings
from kactus_data.jobs.gold_sync import gold_backfill, gold_sync
from kactus_data.jobs.sync_queue import SyncJobDeps, SyncJobView
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_gold.sync import (
    gold_backfill_dedup_key,
    gold_backfill_min,
    gold_sync_dedup_key,
)

cli = AsyncTyper(help="Gold backfill & sync-now operations")


def _deps(db_path: str | None) -> SyncJobDeps:
    settings = get_settings()
    storage = DuckDBStorage(db_path or settings.db_path)
    # Handlers use only .storage; db/providers are unused by the gold handlers.
    return SyncJobDeps(db=None, storage=storage, providers={})


async def _print_progress(done: int, total: int, cursor: str | None = None) -> None:
    pct = round(done * 100 / total) if total else 0
    typer.echo(f"  [{done:>3}/{total}] {pct:>3}%  {cursor or ''}")


@cli.command()
def backfill(
    source: str = typer.Option(..., "--source", help="sjc | yahoo | mihong"),
    from_: str = typer.Option(
        "", "--from", help="Start YYYY-MM-DD (default: the source's earliest)"
    ),
    to: str = typer.Option("", "--to", help="End YYYY-MM-DD (default: today)"),
    code: str = typer.Option("", "--code", help="Override code (mihong only)"),
    db_path: str = typer.Option(
        "", "--db-path", help="DuckDB path (default: settings)"
    ),
):
    """Backfill one gold series over a date range, running the handler inline."""
    source = source.lower()
    if source not in ("sjc", "yahoo", "mihong"):
        typer.secho(f"Unknown source: {source}", fg=typer.colors.RED)
        raise typer.Exit(1)

    date_from = date.fromisoformat(from_) if from_ else gold_backfill_min(source)
    date_to = date.fromisoformat(to) if to else date.today()
    params = {
        "source": source,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
    }
    if code:
        params["code"] = code

    view = SyncJobView(
        id=0,
        job_type="gold_backfill",
        dedup_key=gold_backfill_dedup_key(source, code or None),
        params=params,
        cursor=None,
        progress_done=0,
        progress_total=0,
    )
    typer.echo(f"Backfilling {source} {date_from} → {date_to} ...")
    result = asyncio.run(gold_backfill(view, _deps(db_path or None), _print_progress))
    typer.secho(f"✓ {result}", fg=typer.colors.GREEN)


@cli.command()
def sync(
    source: str = typer.Option("all", "--source", help="all | sjc | mihong | yahoo"),
    db_path: str = typer.Option(
        "", "--db-path", help="DuckDB path (default: settings)"
    ),
):
    """Fetch current gold quotes now (refresh board + log intraday ticks)."""
    view = SyncJobView(
        id=0,
        job_type="gold_sync",
        dedup_key=gold_sync_dedup_key(source.lower()),
        params={"source": source.lower()},
        cursor=None,
        progress_done=0,
        progress_total=0,
    )
    typer.echo(f"Syncing gold ({source}) now ...")
    result = asyncio.run(gold_sync(view, _deps(db_path or None), _print_progress))
    typer.secho(f"✓ {result}", fg=typer.colors.GREEN)
