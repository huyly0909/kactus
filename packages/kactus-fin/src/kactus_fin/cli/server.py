"""Server start commands for kactus-fin."""

import typer
import uvicorn

from kactus_fin.cli import cli
from kactus_fin.config import get_settings


@cli.command()
def dev(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(None, help="Bind port (default: from config)"),
):
    """Start development server with hot-reload."""
    settings = get_settings()
    uvicorn.run(
        app="kactus_fin.app:app",
        host=host,
        port=port or settings.port,
        reload=True,
        log_level="debug",
    )


@cli.command()
def stag(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(None, help="Bind port (default: from config)"),
    workers: int = typer.Option(2, help="Number of workers"),
):
    """Start staging server."""
    settings = get_settings()
    uvicorn.run(
        app="kactus_fin.app:app",
        host=host,
        port=port or settings.port,
        workers=workers,
        log_level="info",
    )


@cli.command()
def prod(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(None, help="Bind port (default: from config)"),
    workers: int = typer.Option(4, help="Number of workers"),
):
    """Start production server."""
    settings = get_settings()
    uvicorn.run(
        app="kactus_fin.app:app",
        host=host,
        port=port or settings.port,
        workers=workers,
        log_level="warning",
    )
