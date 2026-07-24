"""Server start commands for kactus-data-server.

Every mode is fixed at one worker, and there is no ``--workers`` option to pass.
Two processes would mean two DuckDB write handles and two schedulers; making it
configurable would only make it possible to get wrong.
"""

import typer
import uvicorn
from kactus_data_server.cli import cli
from kactus_data_server.config import get_settings


@cli.command()
def dev(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(None, help="Bind port (default: from config)"),
):
    """Start development server with hot-reload."""
    settings = get_settings()
    uvicorn.run(
        app="kactus_data_server.app:app",
        host=host,
        port=port or settings.port,
        reload=True,
        log_level="debug",
    )


@cli.command()
def stag(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(None, help="Bind port (default: from config)"),
):
    """Start staging server (single worker — see module docstring)."""
    settings = get_settings()
    uvicorn.run(
        app="kactus_data_server.app:app",
        host=host,
        port=port or settings.port,
        workers=1,
        log_level="info",
    )


@cli.command()
def prod(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(None, help="Bind port (default: from config)"),
):
    """Start production server (single worker — see module docstring)."""
    settings = get_settings()
    uvicorn.run(
        app="kactus_data_server.app:app",
        host=host,
        port=port or settings.port,
        workers=1,
        log_level="warning",
    )
