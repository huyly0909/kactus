"""
Async SQLAlchemy session management.

Provides :class:`DatabaseSessionManager` — a configurable wrapper around
SQLAlchemy async engine and session creation. Each application creates its
own singleton instance with its own connection settings.

Usage in kactus-fin::

    from kactus_common.database.oltp import DatabaseSessionManager
    from kactus_fin.config import get_settings

    settings = get_settings()
    db = DatabaseSessionManager(database_url=settings.database_url)

    async with db.get_session() as session:
        ...
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import wraps
from inspect import signature
from typing import Any, AsyncContextManager, AsyncIterator, Callable

import orjson
from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm.attributes import InstrumentedAttribute

from kactus_common.exceptions import InvalidArgumentError


def json_dumps(*args, **kwargs) -> str:
    return orjson.dumps(*args, **kwargs).decode()


def json_loads(*args, **kwargs):
    return orjson.loads(*args, **kwargs)


def convert_to_async_url(url: str) -> str:
    """Convert database URL to use async driver.

    Converts synchronous drivers to async equivalents:
    - PostgreSQL: psycopg2 -> asyncpg
    - MySQL/MariaDB: pymysql/mariadbconnector -> asyncmy
    """
    if url.startswith("sqlite"):
        return url

    # PostgreSQL conversions
    if url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    elif url.startswith("postgres+psycopg2://"):
        url = url.replace("postgres+psycopg2://", "postgresql+asyncpg://")
    elif url.startswith("postgresql://") and "+" not in url.split("://")[0]:
        url = url.replace("postgresql://", "postgresql+asyncpg://")
    elif url.startswith("postgres://") and "+" not in url.split("://")[0]:
        url = url.replace("postgres://", "postgresql+asyncpg://")
    # MySQL/MariaDB conversions
    elif url.startswith("mariadb+mariadbconnector://"):
        url = url.replace("mariadb+mariadbconnector://", "mysql+asyncmy://")
    elif url.startswith("mysql+pymysql://"):
        url = url.replace("mysql+pymysql://", "mysql+asyncmy://")
    elif url.startswith("mariadb+pymysql://"):
        url = url.replace("mariadb+pymysql://", "mysql+asyncmy://")
    elif url.startswith("mysql://") and "+" not in url.split("://")[0]:
        url = url.replace("mysql://", "mysql+asyncmy://")
    elif url.startswith("mariadb://") and "+" not in url.split("://")[0]:
        url = url.replace("mariadb://", "mysql+asyncmy://")

    return url


class DatabaseSessionManager:
    """Configurable async SQLAlchemy session manager.

    Each application (kactus-fin, kactus-fin-gateway, …) creates its own
    instance with its own connection settings. No global settings import.

    Args:
        database_url: SQLAlchemy-compatible database URL.
        echo: Echo SQL statements to the log.
        pool_size: Connection pool size.
    """

    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 5,
    ) -> None:
        self._database_url = convert_to_async_url(database_url)
        self._echo = echo
        self._pool_size = pool_size
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker | None = None

    @property
    def engine(self) -> AsyncEngine:
        """Lazily create and return the async engine."""
        if self._engine is None:
            use_pool_pre_ping = self._database_url.startswith("sqlite")
            self._engine = create_async_engine(
                url=self._database_url,
                echo=self._echo,
                pool_size=self._pool_size,
                pool_pre_ping=use_pool_pre_ping,
                json_serializer=json_dumps,
                json_deserializer=json_loads,
            )
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker:
        """Lazily create and return the session factory."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.engine, autoflush=False, expire_on_commit=False
            )
        return self._session_factory

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """Context manager that yields a session, auto-commits on success and
        rolls back on exception."""
        session: AsyncSession = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    def provide_session(self, fn: Callable[..., Any]):
        """Decorator that auto-injects a ``session`` argument when not provided."""
        parameters = signature(fn).parameters
        has_session = "session" in parameters
        session_has_default = (
            has_session
            and parameters["session"].default is not parameters["session"].empty
            and parameters["session"].default is not None
        )
        session_args_idx = tuple(parameters).index("session") if has_session else None

        @wraps(fn)
        async def wrapper(*args, **kwargs) -> Any:
            if not has_session or session_has_default:
                return await fn(*args, **kwargs)

            if session_args_idx is not None and session_args_idx < len(args):
                if args[session_args_idx] is not None:
                    return await fn(*args, **kwargs)

            if "session" in kwargs and kwargs["session"]:
                return await fn(*args, **kwargs)

            async with self.get_session() as session:
                if session_args_idx < len(args):
                    args = list(args)
                    args[session_args_idx] = session
                    args = tuple(args)
                else:
                    kwargs["session"] = session
                return await fn(*args, **kwargs)

        return wrapper

    async def close(self) -> None:
        """Dispose the engine and release all connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None


# ---------------------------------------------------------------------------
# Standalone query helpers (stateless — take a session as argument)
# ---------------------------------------------------------------------------


def is_column_involve_query(query: Select, field_name: str) -> bool:
    """Check if *field_name* is referenced by *query*."""
    field_name = field_name.strip()

    def _check_columns(obj):
        if hasattr(obj, "columns"):
            for column in obj.columns:
                if column.name == field_name:
                    return True
        return False

    if query.column_descriptions:
        primary_entity = query.column_descriptions[0].get("entity")
        if primary_entity and hasattr(primary_entity, field_name):
            potential_attr = getattr(primary_entity, field_name)
            if isinstance(potential_attr, InstrumentedAttribute):
                return True
        for col_desc in query.column_descriptions:
            if col_desc.get("name") == field_name:
                if col_desc.get("expr") is not None:
                    return True

    if hasattr(query, "selectable") and hasattr(query.selectable, "columns"):
        if _check_columns(query.selectable):
            return True

    if hasattr(query, "froms") and query.froms:
        for from_clause in query.froms:
            if _check_columns(from_clause):
                return True
            if hasattr(from_clause, "left") and hasattr(from_clause, "right"):
                for side in [from_clause.left, from_clause.right]:
                    if _check_columns(side):
                        return True

    return False


async def paginator(
    session: AsyncSession,
    query: Select,
    page: int = None,
    page_size: int = None,
    order_by: str = "id",
    force_page_size: bool = False,
    no_page: bool = False,
    unique: bool = False,
) -> tuple[list, int]:
    """Execute *query* with optional pagination and ordering."""
    total = await session.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    )

    if order_by:
        order_field_name: str = order_by.lstrip("+-").strip()
        order_direction = "desc" if order_by.startswith("-") else "asc"
    else:
        order_field_name = "id"
        order_direction = "desc"

    if not is_column_involve_query(query, order_field_name):
        raise InvalidArgumentError(f"invalid order_by field: {order_field_name}")

    order_clause = (
        desc(order_field_name) if order_direction == "desc" else asc(order_field_name)
    )

    if no_page:
        query = query.order_by(order_clause)
    else:
        if page < 1:
            page = 1
        if page_size <= 0:
            page_size = 10
        if page_size >= 100 and not force_page_size:
            page_size = 100
        offset = 0 if page == 1 else (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(order_clause)

    result = await session.execute(query)
    if unique:
        result = result.unique()
    result = result.all()

    single_len = len(result[0]) if result else 1
    if single_len == 1:
        result = [t[0] for t in result]
    return result, total
