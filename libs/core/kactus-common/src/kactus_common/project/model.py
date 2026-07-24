"""Project and ProjectMember ORM models."""

from __future__ import annotations

from kactus_common.database.oltp.models import (
    AuditCreatorMixin,
    Base,
    LogicalDeleteMixin,
    ModelMixin,
)
from kactus_common.database.oltp.types import UnsignedBigInt
from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .const import DefaultRole, ProjectStatus


class Project(Base, ModelMixin, AuditCreatorMixin, LogicalDeleteMixin):
    """A project that users can be assigned to."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default=ProjectStatus.ACTIVE)


class ProjectMember(Base, ModelMixin):
    """Association between a user and a project with a role."""

    __tablename__ = "project_members"

    project_id: Mapped[UnsignedBigInt] = mapped_column(index=True)
    user_id: Mapped[UnsignedBigInt] = mapped_column(index=True)
    role: Mapped[str] = mapped_column(String(50), default=DefaultRole.MEMBER)

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
