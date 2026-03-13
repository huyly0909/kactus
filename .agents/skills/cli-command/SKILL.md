---
name: cli-command
description: Use when adding or modifying CLI commands in any kactus package. Covers AsyncTyper, command registration, and manage.py entry point.
---

# CLI Command Skill

## Framework

All CLI commands use **Typer** via the `AsyncTyper` wrapper from `kactus_common.cli`.

## Entry Point

All commands are accessed via the root `manage.py`:

```bash
python manage.py fin <command>          # kactus-fin commands
python manage.py fin-gw <command>       # kactus-fin-gateway commands
python manage.py data <command>         # kactus-data commands
```

## Creating a New CLI Command

### 1. Create the command file

```python
# packages/kactus-fin/src/kactus_fin/cli/my_command.py
"""Description of what these commands do."""

from __future__ import annotations

import typer
from kactus_common.cli import AsyncTyper
from kactus_common.database.oltp.session import get_db

cli = AsyncTyper(help="My feature commands")


@cli.command()
async def do_something(
    name: str = typer.Option(..., prompt=True, help="Item name"),
    dry_run: bool = typer.Option(False, help="Preview without changes"),
):
    """Do something useful."""
    db = get_db()

    async with db.get_session() as session:
        # ... business logic ...
        typer.echo("✅ Done!")

    await db.close()
```

### 2. Register in the package's CLI `__init__.py`

```python
# packages/kactus-fin/src/kactus_fin/cli/__init__.py
from kactus_common.cli import AsyncTyper

cli = AsyncTyper(help="Kactus Fin CLI")

# Import and register sub-commands
from .server import cli as server_cli
from .db import cli as db_cli
from .my_command import cli as my_cli   # ← add this

cli.add_typer(server_cli, name="server")
cli.add_typer(db_cli, name="db")
cli.add_typer(my_cli, name="my-feature")   # ← add this
```

### 3. The root `manage.py` already picks it up

`manage.py` imports the package-level `cli` and registers it:

```python
# manage.py (already exists, no changes needed usually)
from kactus_fin.cli import cli as fin_cli
app.add_typer(fin_cli, name="fin", help="Kactus Fin — main API server")
```

### Usage:

```bash
python manage.py fin my-feature do-something --name "hello"
```

## Patterns

- Use `AsyncTyper` from `kactus_common.cli` for async commands
- Use `typer.Option(...)` for named options with `prompt=True` for interactive input
- Use `typer.Argument(...)` for positional args
- Use `typer.echo()` for output (not `print()`)
- Use emoji prefixes: `✅` success, `❌` error, `⚠️` warning
- Call `await db.close()` at the end of DB-using commands
- Use `typer.Exit(code=1)` for error exits

## Settings Initialization in CLI

If the command needs app settings, initialize them first:

```python
@cli.command()
async def my_command():
    """Command that needs settings."""
    from kactus_fin.config import get_settings
    get_settings()  # registers settings in the global registry

    # Now kactus_common.config.settings works
    ...
```
