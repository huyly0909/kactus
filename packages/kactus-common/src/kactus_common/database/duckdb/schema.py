from typing import List, Optional

from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from pydantic import BaseModel

#: Default DECIMAL shape for money columns.  20 integer digits comfortably holds
#: VND market caps (~1e15) and 4 decimals cover sub-unit prices.
DEFAULT_MONEY_PRECISION = 24
DEFAULT_MONEY_SCALE = 4


class Column(BaseModel):
    name: str
    data_type: DataType
    is_primary_key: bool = False
    is_nullable: bool = True
    default_value: Optional[str] = None
    #: DECIMAL only — defaults to DECIMAL(24,4) when omitted.
    precision: Optional[int] = None
    scale: Optional[int] = None

    @property
    def sql_type(self) -> str:
        """DuckDB type for DDL — expands DECIMAL to ``DECIMAL(precision,scale)``."""
        if self.data_type is DataType.DECIMAL:
            precision = self.precision or DEFAULT_MONEY_PRECISION
            scale = self.scale if self.scale is not None else DEFAULT_MONEY_SCALE
            return f"DECIMAL({precision},{scale})"
        return str(self.data_type)


class Table(BaseModel):
    name: str
    columns: list[Column]
    update_strategy: UpdateStrategy = UpdateStrategy.REPLACE
    partition_columns: Optional[List[str]] = None  # For INSERT_OVERWRITE strategy

    def get_primary_key_columns(self) -> List[str]:
        """Get list of primary key column names."""
        return [col.name for col in self.columns if col.is_primary_key]

    def get_column_by_name(self, name: str) -> Optional[Column]:
        """Get a column by its name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None
