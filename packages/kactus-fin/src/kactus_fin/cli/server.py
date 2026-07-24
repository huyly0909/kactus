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
    workers: int = typer.Option(1, help="Number of workers (keep 1 — see note below)"),
):
    """Start staging server.

    ``workers`` defaults to 1 on purpose: the portfolio scheduler, the SSE broker
    and the Zalo PA QR-login session store all live in-process. See :func:`prod`.
    """
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
    workers: int = typer.Option(1, help="Number of workers (keep 1 — see note below)"),
):
    """Start production server.

    ``workers`` defaults to 1 and raising it is a correctness bug today, not a
    tuning knob: each worker starts its own portfolio APScheduler (N workers ⇒ N
    duplicate crawls burning the vnstock rate limit, plus DuckDB write-lock
    contention), owns a private SSE broker (a client only hears from the worker it
    landed on), and owns a private Zalo PA QR-login session store (the 5-step flow
    breaks when steps round-robin across workers). Scale-out needs Redis pub/sub
    and a shared session store first.
    """
    settings = get_settings()
    uvicorn.run(
        app="kactus_fin.app:app",
        host=host,
        port=port or settings.port,
        workers=workers,
        log_level="warning",
    )
