"""Kactus Common - Shared utilities, database clients, and common infrastructure."""

# ORM model modules in this package — used by load_models() for Alembic autogenerate
MODELS: list[str] = [
    "kactus_common.user.model",
    "kactus_common.project.model",
    "kactus_common.portfolio.model",
]

# DuckDB
from kactus_common.database.duckdb.client import DatabaseClient
from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table

# OLTP
from kactus_common.database.oltp.session import DatabaseSessionManager

# Exceptions
from kactus_common.exceptions import (
    ConfigurationError,
    DatabaseError,
    DataSourceError,
    InvalidArgumentError,
    KactusException,
    NotFoundError,
)

# Schemas
from kactus_common.schemas import BaseSchema, Pagination, ResponseModel

__all__ = [
    # DuckDB
    "DatabaseClient",
    "Column",
    "Table",
    "DataType",
    "UpdateStrategy",
    # OLTP
    "DatabaseSessionManager",
    # Exceptions
    "KactusException",
    "InvalidArgumentError",
    "NotFoundError",
    "ConfigurationError",
    "DatabaseError",
    "DataSourceError",
    # Schemas
    "BaseSchema",
    "ResponseModel",
    "Pagination",
]
