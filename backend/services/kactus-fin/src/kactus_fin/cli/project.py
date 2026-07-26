"""Project management CLI commands for kactus-fin."""

from __future__ import annotations

import typer
from kactus_common.cli import AsyncTyper
from kactus_common.database.oltp.session import get_db
from kactus_common.portfolio.model import CrawlRun, Portfolio, PortfolioItem
from kactus_common.project.service import ProjectService
from kactus_common.user.model import User
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
