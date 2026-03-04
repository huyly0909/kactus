#!/usr/bin/env python3
"""Tests for DuckDBStorage."""

import os

import pandas as pd
import pytest

from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table
from kactus_data.storage.duckdb import DuckDBStorage


class TestDuckDBStorage:
    """Tests for DuckDBStorage."""

    def test_init(self, tmp_path):
        db = DuckDBStorage(str(tmp_path / "test.duckdb"))
        assert db.db_path == str(tmp_path / "test.duckdb")
        db.close()

    def test_list_tables_empty(self, tmp_path):
        db = DuckDBStorage(str(tmp_path / "test.duckdb"))
        tables = db.list_tables()
        assert tables == []
        db.close()

    def test_store_and_list(self, tmp_path):
        db = DuckDBStorage(str(tmp_path / "test.duckdb"))
        table = Table(
            name="test_prices",
            columns=[
                Column(name="code", data_type=DataType.STRING),
                Column(name="price", data_type=DataType.FLOAT),
            ],
        )
        df = pd.DataFrame({"code": ["SJC", "999"], "price": [72.5, 73.0]})
        rows = db.store(table, df, UpdateStrategy.REPLACE)
        assert rows == 2
        assert "test_prices" in db.list_tables()
        db.close()

    def test_query(self, tmp_path):
        db = DuckDBStorage(str(tmp_path / "test.duckdb"))
        table = Table(
            name="prices",
            columns=[
                Column(name="code", data_type=DataType.STRING),
                Column(name="price", data_type=DataType.FLOAT),
            ],
        )
        df = pd.DataFrame({"code": ["SJC"], "price": [72.5]})
        db.store(table, df, UpdateStrategy.REPLACE)

        result = db.query("SELECT * FROM prices")
        assert len(result) == 1
        assert result.iloc[0]["code"] == "SJC"
        db.close()

    def test_export_table(self, tmp_path):
        db = DuckDBStorage(str(tmp_path / "test.duckdb"))
        table = Table(
            name="prices",
            columns=[Column(name="code", data_type=DataType.STRING)],
        )
        db.store(table, pd.DataFrame({"code": ["SJC"]}), UpdateStrategy.REPLACE)

        output_dir = str(tmp_path / "backups")
        path = db.export_table("prices", output_dir, "parquet")
        assert path.endswith(".parquet")
        assert "prices" in path
        assert os.path.exists(path)
        db.close()
