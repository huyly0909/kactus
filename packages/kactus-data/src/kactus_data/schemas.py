"""Shared schemas for kactus-data ETL pipelines."""

from kactus_common.schemas import BaseSchema


class SyncDataResponse(BaseSchema):
    """Response from a data source sync operation."""

    success: bool
    data_source: str
    code: str
    start_date: str
    end_date: str
    data: dict | list | None = None
    error: dict | str | None = None
    timestamp: str


class SyncResult(BaseSchema):
    """Result of a full sync-and-store pipeline run."""

    data_source: str
    rows_fetched: int
    rows_stored: int
    table_name: str
    duration_ms: float
    success: bool
    error: str | None = None
