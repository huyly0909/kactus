#!/usr/bin/env python3
"""Tests for SyncDataResponse and SyncResult schemas."""

import pytest

from kactus_data.schemas import SyncDataResponse, SyncResult


class TestSyncDataResponse:
    """Tests for the SyncDataResponse schema."""

    def test_create_success_response(self):
        response = SyncDataResponse(
            success=True,
            data_source="test_source",
            code="SJC",
            start_date="2024-01-01",
            end_date="2024-01-31",
            data={"prices": [100, 200]},
            timestamp="2024-01-31T12:00:00",
        )
        assert response.success is True
        assert response.data_source == "test_source"
        assert response.code == "SJC"
        assert response.data == {"prices": [100, 200]}
        assert response.error is None

    def test_create_error_response(self):
        response = SyncDataResponse(
            success=False,
            data_source="test_source",
            code="SJC",
            start_date="2024-01-01",
            end_date="2024-01-31",
            error="Connection timeout",
            timestamp="2024-01-31T12:00:00",
        )
        assert response.success is False
        assert response.error == "Connection timeout"
        assert response.data is None

    def test_error_as_dict(self):
        response = SyncDataResponse(
            success=False,
            data_source="test_source",
            code="SJC",
            start_date="2024-01-01",
            end_date="2024-01-31",
            error={"message": "Failed", "status_code": 500},
            timestamp="2024-01-31T12:00:00",
        )
        assert isinstance(response.error, dict)
        assert response.error["status_code"] == 500

    def test_serialization(self):
        response = SyncDataResponse(
            success=True,
            data_source="mihong",
            code="999",
            start_date="2024-01-01",
            end_date="2024-01-31",
            data={},
            timestamp="2024-01-31T12:00:00",
        )
        data = response.model_dump()
        assert data["success"] is True
        assert data["data_source"] == "mihong"

    def test_inherits_base_schema(self):
        from kactus_common.schemas import BaseSchema
        assert issubclass(SyncDataResponse, BaseSchema)


class TestSyncResult:
    """Tests for SyncResult schema."""

    def test_success_result(self):
        result = SyncResult(
            data_source="mihong",
            rows_fetched=100,
            rows_stored=100,
            table_name="gold_prices",
            duration_ms=1234.5,
            success=True,
        )
        assert result.success is True
        assert result.rows_fetched == 100
        assert result.error is None

    def test_error_result(self):
        result = SyncResult(
            data_source="mihong",
            rows_fetched=0,
            rows_stored=0,
            table_name="gold_prices",
            duration_ms=50.0,
            success=False,
            error="Connection refused",
        )
        assert result.success is False
        assert result.error == "Connection refused"
