"""Database migration commands for kactus-fin (Alembic wrapper)."""

import os

from typer import Context, Option, Typer

from alembic import command
from alembic.config import Config

cli = Typer()

# Alembic config lives next to this package's source
_PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_INI = os.path.join(_PACKAGE_DIR, "alembic.ini")


def _get_config(ini_path: str = _DEFAULT_INI) -> Config:
    cfg = Config(ini_path)
    # Override script_location to point to this package's migrations
    migrations_dir = os.path.join(_PACKAGE_DIR, "migrations")
    cfg.set_main_option("script_location", migrations_dir)
    return cfg


@cli.callback()
def main(ctx: Context, config: str = Option(_DEFAULT_INI, help="Alembic config path")):
    """Database migration commands."""
    ctx.obj = {"config": _get_config(config)}


@cli.command()
def init(ctx: Context):
    """Initialize migrations directory."""
    migrations_dir = os.path.join(_PACKAGE_DIR, "migrations")
    command.init(ctx.obj["config"], migrations_dir)


@cli.command()
def migrate(ctx: Context, message: str = Option(..., "-m", help="Migration message")):
    """Auto-generate a new migration revision."""
    command.revision(ctx.obj["config"], message=message, autogenerate=True)


@cli.command()
def upgrade(ctx: Context, revision: str = Option("head", help="Target revision")):
    """Upgrade database to a revision (default: head)."""
    command.upgrade(ctx.obj["config"], revision)


@cli.command()
def downgrade(ctx: Context, revision: str = Option(..., help="Target revision")):
    """Downgrade database to a revision."""
    command.downgrade(ctx.obj["config"], revision)


@cli.command()
def current(ctx: Context):
    """Show current database revision."""
    command.current(ctx.obj["config"])


@cli.command()
def history(ctx: Context):
    """Show migration history."""
    command.history(ctx.obj["config"])
