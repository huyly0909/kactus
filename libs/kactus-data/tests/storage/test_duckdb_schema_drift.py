"""Schema drift detection and rebuild for DuckDB tables.

Tables are created with ``CREATE TABLE IF NOT EXISTS``, so a definition change
never reaches a database that already holds the table. Since inserts are
positional, undetected drift misaligns values rather than erroring cleanly —
these tests pin the detection that makes the gap visible.
"""

from decimal import Decimal

import pandas as pd
import pytest
from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table
from kactus_data.storage.duckdb import DuckDBStorage


def _table(columns: list[Column]) -> Table:
    return Table(name="prices", columns=columns, update_strategy=UpdateStrategy.UPSERT)


OLD = _table(
    [
        Column(
            name="code",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(name="buy_price", data_type=DataType.FLOAT),
    ]
)

NEW = _table(
    [
        Column(
            name="code",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(name="buy_price", data_type=DataType.DECIMAL),
        Column(name="unit", data_type=DataType.STRING),
    ]
)


@pytest.fixture
def storage(tmp_path) -> DuckDBStorage:
    return DuckDBStorage(str(tmp_path / "drift.duckdb"))


def test_no_drift_reported_for_missing_table(storage):
    """A table that was never created is 'not yet built', not 'drifted'."""
    assert storage.schema_drift(NEW) == []


def test_no_drift_when_definition_matches(storage):
    storage.store(
        NEW, pd.DataFrame([{"code": "SJC", "buy_price": 1.0, "unit": "VND/luong"}])
    )
    assert storage.schema_drift(NEW) == []


def test_type_aliases_are_not_drift(storage):
    """STRING is declared, VARCHAR is reported back — the same type."""
    storage.store(
        NEW, pd.DataFrame([{"code": "SJC", "buy_price": 1.0, "unit": "VND/luong"}])
    )
    assert not any("code" in d for d in storage.schema_drift(NEW))


def test_detects_type_change_and_new_column(storage):
    storage.store(OLD, pd.DataFrame([{"code": "SJC", "buy_price": 1.0}]))
    drift = storage.schema_drift(NEW)

    assert "buy_price: FLOAT → DECIMAL(24,4)" in drift
    assert "missing column unit (STRING)" in drift


def test_detects_removed_column(storage):
    storage.store(
        NEW, pd.DataFrame([{"code": "SJC", "buy_price": 1.0, "unit": "VND/luong"}])
    )
    drift = storage.schema_drift(OLD)

    assert any(d.startswith("extra column unit") for d in drift)


def test_recreate_clears_drift_and_applies_decimal(storage):
    """The point of the rebuild: money actually lands in a DECIMAL column."""
    storage.store(OLD, pd.DataFrame([{"code": "SJC", "buy_price": 136_571_424.0}]))
    storage.recreate_table(NEW)

    assert storage.schema_drift(NEW) == []
    storage.store(
        NEW,
        pd.DataFrame(
            [{"code": "SJC", "buy_price": 136_571_424.0, "unit": "VND/luong"}]
        ),
    )
    value = storage.query("SELECT buy_price FROM prices")["buy_price"][0]
    assert isinstance(value, Decimal)
    assert value == Decimal("136571424")


def test_recreate_discards_existing_rows(storage):
    """Rebuild is destructive — callers must re-run the crawl afterwards."""
    storage.store(OLD, pd.DataFrame([{"code": "SJC", "buy_price": 1.0}]))
    storage.recreate_table(NEW)
    assert storage.query("SELECT COUNT(*) AS n FROM prices")["n"][0] == 0


def test_float_column_loses_precision_that_decimal_keeps(storage):
    """Why money is DECIMAL: FLOAT is exact only below 2^24 (~16.7M).

    Gold at ~1.4e8 VND/lượng is well past that, so a FLOAT column silently
    rounds the stored price.
    """
    storage.store(OLD, pd.DataFrame([{"code": "SJC", "buy_price": 136_571_425.0}]))
    as_float = storage.query("SELECT buy_price FROM prices")["buy_price"][0]
    assert as_float != 136_571_425.0  # rounded by float32

    storage.recreate_table(NEW)
    storage.store(
        NEW,
        pd.DataFrame(
            [{"code": "SJC", "buy_price": 136_571_425.0, "unit": "VND/luong"}]
        ),
    )
    as_decimal = storage.query("SELECT buy_price FROM prices")["buy_price"][0]
    assert as_decimal == Decimal("136571425")
