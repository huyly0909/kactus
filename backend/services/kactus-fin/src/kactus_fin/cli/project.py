"""Project management CLI commands for kactus-fin."""

from __future__ import annotations

import typer
from kactus_common.cli import AsyncTyper
from kactus_common.database.oltp.session import get_db
from kactus_common.portfolio.model import CrawlRun, Portfolio, PortfolioItem
from kactus_common.project.model import Project, ProjectMember
from kactus_common.project.service import ProjectService
from kactus_common.user.model import User
from kactus_common.user.service import UserService
from kactus_fin.action.model import ActionToken
from kactus_notification.model import NotificationChannel, NotificationLog
from sqlalchemy import select, update

cli = AsyncTyper(help="Project management commands")


@cli.callback()
def _bootstrap() -> None:
    """Register fin settings before any project command (see cli/user.py)."""
    from kactus_fin.config import get_settings

    get_settings()


@cli.command(name="backfill-personal-projects")
async def backfill_personal_projects() -> None:
    """Provision a personal project per non-admin user and move their data into it.

    Idempotent: every UPDATE is guarded by ``project_id IS NULL`` and
    ``ensure_personal_project`` is keyed on a deterministic code, so re-running
    is safe. Run once after deploying project scoping.
    """
    db = get_db()
    created = 0

    async with db.get_session() as session:
        users = await User.all(session)
        for user in users:
            project = await ProjectService.ensure_personal_project(session, user=user)
            if project is None:  # superuser — skipped
                continue
            created += 1

            # Primary entities scoped by owner/user.
            await session.execute(
                update(Portfolio)
                .where(Portfolio.owner_id == user.id, Portfolio.project_id.is_(None))
                .values(project_id=project.id)
                .execution_options(synchronize_session=False)
            )
            await session.execute(
                update(NotificationChannel)
                .where(
                    NotificationChannel.owner_id == user.id,
                    NotificationChannel.project_id.is_(None),
                )
                .values(project_id=project.id)
                .execution_options(synchronize_session=False)
            )
            await session.execute(
                update(ActionToken)
                .where(ActionToken.user_id == user.id, ActionToken.project_id.is_(None))
                .values(project_id=project.id)
                .execution_options(synchronize_session=False)
            )

        # Child rows inherit project_id from their parent (run once, globally).
        await session.execute(
            update(PortfolioItem)
            .where(PortfolioItem.project_id.is_(None))
            .values(
                project_id=select(Portfolio.project_id)
                .where(Portfolio.id == PortfolioItem.portfolio_id)
                .scalar_subquery()
            )
            .execution_options(synchronize_session=False)
        )
        await session.execute(
            update(CrawlRun)
            .where(CrawlRun.project_id.is_(None), CrawlRun.portfolio_id.isnot(None))
            .values(
                project_id=select(Portfolio.project_id)
                .where(Portfolio.id == CrawlRun.portfolio_id)
                .scalar_subquery()
            )
            .execution_options(synchronize_session=False)
        )
        await session.execute(
            update(NotificationLog)
            .where(NotificationLog.project_id.is_(None))
            .values(
                project_id=select(NotificationChannel.project_id)
                .where(NotificationChannel.id == NotificationLog.channel_id)
                .scalar_subquery()
            )
            .execution_options(synchronize_session=False)
        )

    typer.echo(f"✅ Backfill complete — {created} personal project(s) ensured.")
    await db.close()


@cli.command(name="repair-owners")
async def repair_owners(
    assign_to: str = typer.Option(
        "",
        "--assign-to",
        help="Email to fall back to when a project's creator no longer exists",
    ),
    prune_members: bool = typer.Option(
        False,
        "--prune-members",
        help="Also delete membership rows whose user or project is gone",
    ),
    confirm: bool = typer.Option(
        False, "--confirm", help="Actually apply (otherwise a dry-run report)"
    ),
) -> None:
    """Report — and optionally repair — projects that have lost their owner.

    Ownership is a ``ProjectMember`` row with ``role='owner'``; there is no
    ``projects.owner_id`` column and the schema carries no foreign keys, so a
    row deleted out of band (a hand-rolled test cleanup, a restored dump) can
    leave a project nobody owns. Nothing in the product does this — the guards
    in ``ProjectService`` see to that — which is exactly why the repair lives
    here rather than in an endpoint.

    Idempotent. Dry-run by default::

        python manage.py fin project repair-owners
        python manage.py fin project repair-owners --assign-to admin@x.com --confirm
        python manage.py fin project repair-owners --prune-members --confirm
    """
    db = get_db()
    fallback: User | None = None
    repaired = 0
    pruned = 0

    async with db.get_session() as session:
        if assign_to:
            fallback = await UserService.get_by_email(session, assign_to.strip())
            if fallback is None:
                typer.secho(f"❌ No user with email {assign_to!r}", fg=typer.colors.RED)
                await db.close()
                raise typer.Exit(code=1)

        live_user_ids = {u.id for u in await User.all(session)}

        # --- projects with no OWNER row -----------------------------------
        projects = await ProjectService.list_all(session)
        ownerless = [
            p for p in projects if not await ProjectService.owner_ids(session, p.id)
        ]
        if not ownerless:
            typer.echo("✅ Every project has an owner.")
        for p in ownerless:
            # Prefer the creator: they are the person the project came from, and
            # ``build_schemas`` has been displaying them all along.
            target = p.created_by if p.created_by in live_user_ids else None
            if target is None and fallback is not None:
                target = fallback.id
            if target is None:
                typer.secho(
                    f"⚠️  {p.id} ({p.code}) — no owner and no live creator; "
                    f"pass --assign-to EMAIL to repair it",
                    fg=typer.colors.YELLOW,
                )
                continue
            typer.echo(f"{'→' if confirm else 'would'} assign {target} to {p.code}")
            if confirm:
                await ProjectService.assign_owner(
                    session, project_id=p.id, user_id=target
                )
                repaired += 1

        # --- membership rows pointing at nothing --------------------------
        # Always *scanned*, only deleted under --prune-members: a report that
        # hides findings behind the flag that fixes them is no report at all.
        # Soft-deleted projects count as existing — they can be restored, and
        # taking their members away would restore them empty. Hence
        # skip_deleted_filter rather than reusing ``projects`` above.
        known_project_ids = set(
            (
                await session.scalars(
                    select(Project.id).execution_options(skip_deleted_filter=True)
                )
            ).all()
        )
        members = list((await session.scalars(select(ProjectMember))).all())
        dangling = [
            m
            for m in members
            if m.user_id not in live_user_ids or m.project_id not in known_project_ids
        ]
        if not dangling:
            typer.echo("✅ Every membership row points at a live user and project.")
        for m in dangling:
            where = f"(project={m.project_id}, user={m.user_id})"
            if not prune_members:
                typer.secho(
                    f"⚠️  membership {m.id} {where} — pass --prune-members to delete it",
                    fg=typer.colors.YELLOW,
                )
                continue
            typer.echo(
                f"{'→' if confirm else 'would'} delete membership {m.id} {where}"
            )
            if confirm:
                await m.delete(session)
                pruned += 1

    if confirm:
        typer.secho(
            f"✅ Repaired {repaired} project(s), pruned {pruned} membership row(s).",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho("Dry run — pass --confirm to apply.", fg=typer.colors.YELLOW)
    await db.close()
