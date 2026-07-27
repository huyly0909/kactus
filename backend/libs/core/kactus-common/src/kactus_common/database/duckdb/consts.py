from enum import StrEnum

# Generic OLAP read cap — the DuckDB tables are unbounded, the APIs over them
# are not. Domain-specific caps (e.g. gold history) live with their domain lib.
MAX_LIMIT = 2000


class DataType(StrEnum):
    """DuckDB data types."""

    INT = "INT"
    # FLOAT is single-precision: exact only for integers below 2^24 (~16.7M).
    # Fine for ratios and volumes; NEVER use it for money.
    FLOAT = "FLOAT"
    DOUBLE = "DOUBLE"
    # Money/prices MUST be DECIMAL — binary floats cannot represent decimal
    # amounts exactly (VND gold at ~1.4e8 silently rounds under FLOAT).
    # Precision/scale come from ``Column.precision``/``Column.scale``.
    DECIMAL = "DECIMAL"
    STRING = "STRING"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIMESTAMP = "TIMESTAMP"
    TIME = "TIME"
    BLOB = "BLOB"


class UpdateStrategy(StrEnum):
    """Database update strategies."""

    APPEND = "APPEND"
    REPLACE = "REPLACE"
    UPSERT = "UPSERT"
    INSERT_OVERWRITE = "INSERT_OVERWRITE"
