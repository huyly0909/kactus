"""
SQLAlchemy ORM base classes and mixins for OLTP databases.

Provides ``Base``, ``ModelMixin``, ``AuditMixin``, ``LogicalDeleteMixin``,
and helpers like ``resolve_table_name`` and ``utcnow``.
"""

from __future__ import annotations

import datetime
import re
import time
import uuid
from typing import TYPE_CHECKING, Any, Iterable, Self, TypeVar, Union, cast

import inflect
from kactus_common.exceptions import NotFoundError
from pydantic import BaseModel
from sqlalchemy import (
    Delete,
    Select,
    delete,
    event,
    exists,
    func,
    insert,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    ORMExecuteState,
    Session,
    declared_attr,
    mapped_column,
    with_loader_criteria,
)
from sqlalchemy_utils import generic_repr

from .snowflake_id import next_id
from .types import DateTimeTzAware, UnsignedBigInt, UUIDList

if TYPE_CHECKING:
    pass

T = TypeVar("T")
T_STMT = TypeVar("T_STMT", bound=Union[Select, Delete])

_p = inflect.engine()

tz_utc = datetime.UTC


def utcnow() -> datetime.datetime:
    """Get the current datetime in UTC. Returns a timezone-aware datetime object."""
    return datetime.datetime.now(tz=tz_utc)


def resolve_table_name(name: str) -> str:
    """Convert CamelCase class name to snake_case plural table name."""
    names = re.split(r"(?=[A-Z])", name)
    names[-1] = _p.plural_noun(names[-1])
    return "_".join([x.lower() for x in names if x])


def ensure_table_prefix(table_name: str, prefix: str | None = None) -> str:
    """Prepend *prefix* to table name if not already present."""
    if not prefix:
        return table_name
    if table_name.startswith(f"{prefix}_"):
        return table_name
    return f"{prefix}_{table_name}"


@generic_repr
class Base(AsyncAttrs, DeclarativeBase):
    type_annotation_map = {
        datetime.datetime: DateTimeTzAware,
        UnsignedBigInt: BIGINT(unsigned=True),
        list[uuid.UUID]: UUIDList,
    }

    # Override in subclass to apply a table prefix
    _table_prefix: str | None = None

    @declared_attr.directive
    def __tablename__(cls):
        name = resolve_table_name(cls.__name__)
        return ensure_table_prefix(name, cls._table_prefix)

    @classmethod
    def get_entity_type(cls) -> str:
        rv = _p.singular_noun(cls.__tablename__)
        if rv is False:
            rv = cls.__tablename__
        return cast(str, rv)

    def get_entity_id(self) -> int:
        if hasattr(self, "id"):
            return self.id
        raise NotImplementedError("Subclasses must implement get_entity_id method.")

    @classmethod
    def select(cls) -> Select:
        return select(cls)

    @classmethod
    def delete_by(cls, *criterion, **kwargs) -> Delete:
        return cls._apply_query_conditions(delete(cls), *criterion, **kwargs)

    @classmethod
    async def get(cls, session: AsyncSession, ident: Any, **kwargs) -> Self | None:
        return await session.get(cls, ident, **kwargs)

    @classmethod
    async def get_or_404(cls, session: AsyncSession, ident: Any, **kwargs) -> Self:
        row = await cls.get(session, ident, **kwargs)
        if not row:
            raise NotFoundError(f"{cls.__name__} record, pk: {ident}")
        return row

    @classmethod
    async def first(cls, session: AsyncSession, **kwargs) -> Self | None:
        result = await session.scalars(cls.select().filter_by(**kwargs).limit(1))
        return result.first()

    @classmethod
    async def first_or_404(cls, session: AsyncSession, **kwargs) -> Self:
        row = await cls.first(session, **kwargs)
        if not row:
            raise NotFoundError(f"{cls.__name__} record")
        return row

    @classmethod
    async def all(
        cls, session: AsyncSession, entities=None, *criterion, **kwargs
    ) -> list:
        if entities is None:
            entities = cls
        use_scalars = True
        if isinstance(entities, tuple):
            stmt = select(*entities)
            use_scalars = False
        else:
            stmt = select(entities)
        stmt = cls._apply_query_conditions(stmt, *criterion, **kwargs)
        if use_scalars:
            result = (await session.scalars(stmt)).all()
        else:
            result = (await session.execute(stmt)).all()
        return cast(list, result)

    @classmethod
    async def exists(cls, session: AsyncSession, *criterion, **kwargs) -> bool:
        stmt = select(exists().select_from(cls))
        stmt = cls._apply_query_conditions(stmt, *criterion, **kwargs)
        return (await session.scalars(stmt)).first()

    @classmethod
    async def get_rowcount(cls, session: AsyncSession, *criterion, **kwargs) -> int:
        stmt = select(func.count()).select_from(cls)
        stmt = cls._apply_query_conditions(stmt, *criterion, **kwargs)
        return await session.scalar(stmt)

    @classmethod
    async def bulk_insert(cls, session: AsyncSession, objs: list[Union[dict, "Base"]]):
        if not objs:
            return
        data = []
        for obj in objs:
            if isinstance(obj, cls):
                data.append(obj.extract_values(obj.get_column_names()))
            else:
                data.append(obj)
        await session.execute(insert(cls.__table__), data)

    async def save(
        self, session: AsyncSession, attribute_names: Iterable[str] | None = None
    ) -> None:
        session.add(self)
        await session.commit()
        if attribute_names is not None:
            await session.refresh(self, attribute_names=attribute_names)

    async def delete(self, session: AsyncSession) -> None:
        await session.delete(self)
        await session.commit()

    def update(self, payload: dict | BaseModel) -> None:
        if isinstance(payload, BaseModel):
            values = payload.model_dump(exclude_unset=True, exclude={})
        else:
            values = payload
        cols = self.__class__.__table__.columns.keys()
        for col in cols:
            if col in values:
                setattr(self, col, values[col])

    @classmethod
    def get_column_names(cls) -> list[str]:
        return cls.__table__.columns.keys()

    @property
    def column_names(self) -> list[str]:
        return self.__class__.get_column_names()

    @staticmethod
    def _apply_query_conditions(stmt: T_STMT, *criterion, **kwargs) -> T_STMT:
        if criterion:
            stmt = stmt.filter(*criterion)
        if kwargs:
            stmt = stmt.filter_by(**kwargs)
        return stmt

    def extract_values(self, cols: Iterable[str]) -> dict[str, Any]:
        result = {}
        for col in cols:
            if hasattr(self, col):
                result[col] = getattr(self, col)
        return result

    def to_dict(self) -> dict[str, Any]:
        return self.extract_values(self.column_names)

    @staticmethod
    def now() -> datetime.datetime:
        return utcnow()

    utcnow = now


class ModelMixin:
    """Standard id + timestamps mixin using snowflake IDs."""

    id: Mapped[UnsignedBigInt] = mapped_column(
        primary_key=True, default=next_id, autoincrement=False
    )
    create_time: Mapped[datetime.datetime | None] = mapped_column(default=utcnow)
    update_time: Mapped[datetime.datetime | None] = mapped_column(
        default=utcnow, onupdate=utcnow
    )

    create_time._creation_order = 9998
    update_time._creation_order = 9999

    @classmethod
    def init(cls, payload: dict[str, Any] | BaseModel = None, **kwargs) -> Self:
        now = utcnow()
        defaults: dict[str, Any] = {
            "id": cls.next_id(),
            "create_time": now,
            "update_time": now,
        }
        if payload is None:
            payload = {}
        if isinstance(payload, BaseModel):
            payload = payload.model_dump()
        defaults.update(payload)
        defaults.update(kwargs)
        return cls(**defaults)

    @staticmethod
    def next_id() -> int:
        return next_id()

    def force_update_time(self) -> None:
        self.update_time = utcnow()

    def __str__(self):
        return f"{self.__class__.__name__}(id={self.id})"

    __repr__ = __str__


class AuditCreatorMixin:
    """Track who created the record."""

    created_by: Mapped[UnsignedBigInt | None] = mapped_column(comment="create user id")
    created_by._creation_order = 8998


class AuditMixin(AuditCreatorMixin):
    """Track who created and last updated the record.

    Uses SQLAlchemy ``before_insert`` / ``before_update`` events to
    automatically populate ``created_by`` and ``updated_by`` from the
    request-scoped ``ContextVar`` set by the auth dependency.
    """

    updated_by: Mapped[UnsignedBigInt | None] = mapped_column(comment="update user id")
    updated_by._creation_order = 8999

    @staticmethod
    def _update_user_id(mapper, connection, target: "AuditMixin"):
        from kactus_common.user.context import get_current_user_id

        user_id = get_current_user_id()
        if user_id is None:
            return
        if not target.created_by:
            target.created_by = user_id
        target.updated_by = user_id

    @classmethod
    def __declare_last__(cls):
        from sqlalchemy import event

        event.listen(cls, "before_insert", cls._update_user_id)
        event.listen(cls, "before_update", cls._update_user_id)


class ExecutionMixin:
    """Track execution start/end times."""

    start_time: Mapped[datetime.datetime] = mapped_column(default=utcnow)
    end_time: Mapped[datetime.datetime | None] = mapped_column(default=None)


class LogicalDeleteMixin:
    """Soft-delete via a ``deleted_timestamp`` column."""

    deleted_timestamp: Mapped[UnsignedBigInt | None] = mapped_column(
        default=0, comment="the timestamp when delete, 0 means not deleted"
    )
    deleted_timestamp._creation_order = 8899

    def mark_as_deleted(self) -> None:
        self.deleted_timestamp = int(time.time())

    @property
    def is_deleted(self) -> bool:
        return self.deleted_timestamp != 0

    @classmethod
    async def bulk_delete(
        cls, session: AsyncSession, ids: list[int], user_id: int | None = None
    ) -> None:
        if not ids:
            return
        values = {
            "deleted_timestamp": int(time.time()),
            "update_time": utcnow(),
        }
        if user_id is not None:
            values["updated_by"] = user_id
        stmt = update(cls).where(cls.id.in_(ids)).values(**values)
        await session.execute(stmt)


@event.listens_for(Session, "do_orm_execute")
def _filter_deleted_records(state: ORMExecuteState):
    """Automatically exclude soft-deleted records from SELECT queries."""
    if state.is_select and not state.is_column_load and not state.is_relationship_load:
        if state.execution_options.get("skip_deleted_filter", False):
            return
        state.statement = state.statement.options(
            with_loader_criteria(
                LogicalDeleteMixin,
                lambda cls: or_(
                    cls.deleted_timestamp == 0, cls.deleted_timestamp.is_(None)
                ),
                include_aliases=True,
            )
        )
