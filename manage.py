"""Kactus CLI — centralized entry point for all package commands.

Usage:
    python manage.py fin dev             # Start kactus-fin in dev mode
    python manage.py fin stag            # Start kactus-fin in staging mode
    python manage.py fin prod            # Start kactus-fin in production mode
    python manage.py fin db migrate -m "add users"
    python manage.py fin db upgrade
    python manage.py fin db downgrade <rev>

    python manage.py fin-gw dev          # Start gateway in dev mode
    python manage.py fin-gw db migrate -m "init"
"""

import typer

app = typer.Typer(
    name="kactus",
    help="Kactus monorepo management CLI",
    no_args_is_help=True,
)


def register_packages():
    from kactus_fin.cli import cli as fin_cli
    from kactus_fin_gateway.cli import cli as gw_cli

    app.add_typer(fin_cli, name="fin", help="Kactus Fin — main API server")
    app.add_typer(gw_cli, name="fin-gw", help="Kactus Fin Gateway — public API server")


register_packages()


if __name__ == "__main__":
    app()
