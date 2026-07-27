"""kactus-data CLI — ETL management commands."""

from kactus_common.cli import AsyncTyper

cli = AsyncTyper(help="Kactus Data — ETL pipelines & backups")


def _add_subcommands():
    from kactus_data.cli import (  # noqa: F401
        backup,
        company,
        finance,
        gold,
        portfolio,
        schema,
        stock,
        sync,
        tz,
    )

    cli.add_typer(backup.cli, name="backup", help="DuckDB backup / export")
    cli.add_typer(schema.cli, name="schema", help="DuckDB schema drift check / rebuild")
    cli.add_typer(tz.cli, name="tz", help="DuckDB timezone (event_dt) backfill")
    cli.add_typer(stock.cli, name="stock", help="Stock price data (OHLCV, listings)")
    cli.add_typer(company.cli, name="company", help="Company overview data")
    cli.add_typer(finance.cli, name="finance", help="Financial statements & ratios")
    cli.add_typer(portfolio.cli, name="portfolio", help="Portfolio crawl & catalog ops")
    cli.add_typer(gold.cli, name="gold", help="Gold backfill & sync-now")


_add_subcommands()
