"""Manual sync trigger commands."""

from datetime import date

import typer

from kactus_data.cli import cli


@cli.command()
def sync(
    domain: str = typer.Argument(help="Domain: gold, stock, coin"),
    source: str = typer.Argument(help="Source name: mihong, ..."),
    code: str = typer.Option(..., "--code", "-c", help="Source-specific code (e.g. SJC, BTC)"),
    start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
    db_path: str = typer.Option("kactus.duckdb", help="DuckDB database path"),
):
    """Manually trigger a data sync from a source into DuckDB.

    Example::

        python manage.py data sync gold mihong -c SJC -s 2024-01-01 -e 2024-01-31
    """
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)

    # Resolve source
    if domain == "gold" and source == "mihong":
        from kactus_data.sources.gold.mihong import MihongGoldSource

        token = typer.prompt("XSRF token", hide_input=True)
        src = MihongGoldSource(xsrf_token=token)
    else:
        typer.secho(
            f"Unknown source: {domain}/{source}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    # Fetch only (no storage wiring by default — user can extend)
    typer.echo(f"Syncing {domain}/{source} [{code}] {start} → {end} ...")
    response = src.sync(start_date, end_date, code)

    if response.success:
        row_count = 0
        if isinstance(response.data, list):
            row_count = len(response.data)
        elif isinstance(response.data, dict):
            for key in ("data", "results", "items", "prices", "records"):
                if key in response.data and isinstance(response.data[key], list):
                    row_count = len(response.data[key])
                    break
        typer.secho(f"✓ Fetched {row_count} records", fg=typer.colors.GREEN)
    else:
        typer.secho(f"✗ Failed: {response.error}", fg=typer.colors.RED)
        raise typer.Exit(1)
