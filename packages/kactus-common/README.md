# kactus-common

Shared library for the Kactus monorepo — provides the DuckDB database client, Pydantic data models, and common constants used across all packages.

## Installation

This package is automatically installed as a workspace dependency. No manual install needed.

```bash
# From the monorepo root
uv sync --all-packages
```

## Usage

### DatabaseClient

A DuckDB client with support for multiple update strategies: `REPLACE`, `APPEND`, `UPSERT`, and `INSERT_OVERWRITE`.

```python
from kactus_common.database.duckdb.client import DatabaseClient
from kactus_common.database.duckdb.schema import Table, Column
from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
import pandas as pd

# Initialize client
db = DatabaseClient("my_data.duckdb")

# Define a table
table = Table(
    name="gold_prices",
    columns=[
        Column(name="date", data_type=DataType.STRING, is_primary_key=True),
        Column(name="code", data_type=DataType.STRING, is_primary_key=True),
        Column(name="price", data_type=DataType.FLOAT),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

# Create the table
db.create_table(table.name, table.columns)

# Insert/update data
data = pd.DataFrame({
    "date": ["2024-01-01", "2024-01-02"],
    "code": ["SJC", "SJC"],
    "price": [72.5, 73.0],
})
db.update_table(table, data)

# Query
result = db.execute("SELECT * FROM gold_prices")
print(result.fetchall())
```

### Update Strategies

| Strategy | Behavior |
|----------|----------|
| `REPLACE` | Drop all existing rows, insert new data |
| `APPEND` | Insert new rows without duplicate checks |
| `UPSERT` | Update rows matching primary key, insert new ones |
| `INSERT_OVERWRITE` | Delete matching partitions, insert new data |

## API Reference

### `kactus_common.database.duckdb`

| Class | Description |
|-------|-------------|
| `DatabaseClient(db_path)` | DuckDB client with CRUD + update strategies |
| `Column` | Pydantic model for column definitions |
| `Table` | Pydantic model for table definitions |
| `DataType` | Enum of DuckDB data types |
| `UpdateStrategy` | Enum: `REPLACE`, `APPEND`, `UPSERT`, `INSERT_OVERWRITE` |



## Testing

```bash
uv run pytest packages/kactus-common/tests/ -v
```
