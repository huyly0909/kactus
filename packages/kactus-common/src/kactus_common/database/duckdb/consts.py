from enum import StrEnum

class DataType(StrEnum):
    """DuckDB data types."""
    INT = "INT"
    FLOAT = "FLOAT"
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
