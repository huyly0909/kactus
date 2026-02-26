"""User management CLI commands for kactus-fin."""

from __future__ import annotations

import typer
from kactus_common.cli import AsyncTyper
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.user.model import User
from kactus_fin.config import get_settings

cli = AsyncTyper(help="User management commands")


async def _create_user(
    email: str,
    username: str,
    name: str,
    password: str,
    status: str = "active",
    is_superuser: bool = False,
):
    """Shared logic for creating a regular or admin user."""
    settings = get_settings()
    db = DatabaseSessionManager(database_url=settings.database_url)

    async with db.get_session() as session:
        # Check for duplicates
        existing = await User.first(session, email=email)
        if existing:
            typer.echo(f"❌ User with email '{email}' already exists.")
            raise typer.Exit(code=1)

        existing = await User.first(session, username=username)
        if existing:
            typer.echo(f"❌ User with username '{username}' already exists.")
            raise typer.Exit(code=1)

        # PasswordHash TypeDecorator auto-hashes the plaintext password
        user = User.init(
            email=email,
            username=username,
            password_hash=password,
            name=name,
            status=status,
            is_superuser=is_superuser,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        role_label = "Admin user" if is_superuser else "User"
        typer.echo(f"✅ {role_label} created successfully!")
        typer.echo(f"   ID:          {user.id}")
        typer.echo(f"   Email:       {user.email}")
        typer.echo(f"   Username:    {user.username}")
        typer.echo(f"   Name:        {user.name}")
        typer.echo(f"   Status:      {user.status}")
        typer.echo(f"   Superuser:   {user.is_superuser}")

    await db.close()


@cli.command()
async def create(
    email: str = typer.Option(..., prompt=True, help="User email"),
    # username: str = typer.Option(..., prompt=True, help="Username"),
    name: str = typer.Option(..., prompt=True, help="Display name"),
    password: str = typer.Option(
        ..., prompt=True, confirmation_prompt=True, hide_input=True, help="Password"
    ),
    status: str = typer.Option("active", help="User status (active/inactive)"),
):
    """Create a new user."""
    await _create_user(
        email=email,
        username=email,
        name=name,
        password=password,
        status=status,
        is_superuser=False,
    )


@cli.command(name="create-admin")
async def create_admin(
    email: str = typer.Option(..., prompt=True, help="Admin email"),
    # username: str = typer.Option(..., prompt=True, help="Admin username"),
    name: str = typer.Option(..., prompt=True, help="Admin display name"),
    password: str = typer.Option(
        ..., prompt=True, confirmation_prompt=True, hide_input=True, help="Password"
    ),
):
    """Create a new admin (superuser) account."""
    await _create_user(
        email=email,
        username=email,
        name=name,
        password=password,
        status="active",
        is_superuser=True,
    )


@cli.command()
async def list():
    """List all users."""
    settings = get_settings()
    db = DatabaseSessionManager(database_url=settings.database_url)

    async with db.get_session() as session:
        users = await User.all(session)
        if not users:
            typer.echo("No users found.")
            return

        typer.echo(
            f"{'ID':<22} {'Email':<30} {'Username':<20} {'Name':<25} {'Super':<6} {'Status':<10}"
        )
        typer.echo("─" * 113)
        for u in users:
            typer.echo(
                f"{u.id:<22} {u.email:<30} {u.username:<20} {u.name:<25} "
                f"{'Yes' if u.is_superuser else 'No':<6} {u.status:<10}"
            )

    await db.close()


@cli.command()
async def reset_password(
    email: str = typer.Option(..., prompt=True, help="User email"),
    password: str = typer.Option(
        ..., prompt=True, confirmation_prompt=True, hide_input=True, help="New password"
    ),
):
    """Reset a user's password."""
    settings = get_settings()
    db = DatabaseSessionManager(database_url=settings.database_url)

    async with db.get_session() as session:
        user = await User.first(session, email=email)
        if not user:
            typer.echo(f"❌ User with email '{email}' not found.")
            raise typer.Exit(code=1)

        # PasswordHash TypeDecorator auto-hashes the plaintext password
        user.password_hash = password
        await user.save(session)

        typer.echo(f"✅ Password reset for '{email}'.")

    await db.close()
