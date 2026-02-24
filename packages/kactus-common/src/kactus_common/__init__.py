"""Kactus Common - Shared utilities, database clients, and common infrastructure."""

# DuckDB
from kactus_common.database.duckdb.client import DatabaseClient
from kactus_common.database.duckdb.schema import Column, Table
from kactus_common.database.duckdb.consts import DataType, UpdateStrategy

# OLTP
from kactus_common.database.oltp.session import DatabaseSessionManager

# Exceptions
from kactus_common.exceptions import (
    KactusException,
    InvalidArgumentError,
    NotFoundError,
    ConfigurationError,
    DatabaseError,
    DataSourceError,
    AuthenticationError,
    PermissionDeniedError,
    ValidationError,
    ConflictError,
    RateLimitError,
    TimeoutError,
    ExternalServiceError,
    InternalError,
)

# Schemas
from kactus_common.schemas import BaseSchema, ResponseModel, Pagination

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
