from pydantic import BaseModel
from typing import Optional, List

from main.database.consts import DataType, UpdateStrategy

class Column(BaseModel):
    name: str
    data_type: DataType
    is_primary_key: bool = False
    is_nullable: bool = True
    default_value: Optional[str] = None
    
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
