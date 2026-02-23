# kactus-data

Data scraping, collection, and ETL pipelines for the Kactus monorepo.

## Installation

Automatically installed as a workspace dependency:

```bash
# From the monorepo root
uv sync --all-packages
```

## Usage

### Creating a Data Source

All data sources extend the `DataSource` abstract base class, providing a consistent interface for fetching data from different providers.

```python
from kactus_data.sources.mihong import MihongDataSource
from datetime import date

# Initialize with API token
source = MihongDataSource(xsrf_token="your-token-here")

# Sync data for a date range
response = source.sync(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31),
    code="SJC",
)

if response.success:
    print(response.data)
else:
    print(f"Error: {response.error}")
```

### Adding a New Data Source

Create a new class extending `DataSource`:

```python
from kactus_data.sources.base import DataSource
from kactus_data.schemas.data_source import SyncDataResponse
from datetime import datetime
from typing import Dict


class MyNewSource(DataSource):
    """Custom data source implementation."""

    def __init__(self, api_key: str):
        super().__init__("https://api.example.com/data", "my_source")
        self.api_key = api_key

    def sync(self, start_date, end_date, code) -> SyncDataResponse:
        params = {"code": code, "from": str(start_date), "to": str(end_date)}
        response = self._make_request(self.base_url, params)
        return SyncDataResponse(
            success=True,
            data_source=self.name,
            code=code,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            data=response.json(),
            timestamp=datetime.now().isoformat(),
        )

    def _format_request_date(self, date_obj, is_end_date=False) -> str:
        return date_obj.isoformat()

    def _get_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _get_cookies(self) -> Dict[str, str]:
        return {}
```

### Storing Fetched Data

Combine with `kactus-common` to persist data:

```python
from kactus_common.database.duckdb.client import DatabaseClient
from kactus_common.database.duckdb.schema import Table, Column
from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_data.sources.mihong import MihongDataSource
import pandas as pd
from datetime import date

# Fetch
source = MihongDataSource(xsrf_token="...")
response = source.sync(date(2024, 1, 1), date(2024, 1, 31), "SJC")

# Store
db = DatabaseClient("kactus.duckdb")
table = Table(
    name="gold_prices",
    columns=[
        Column(name="date", data_type=DataType.STRING, is_primary_key=True),
        Column(name="price", data_type=DataType.FLOAT),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)
db.create_table(table.name, table.columns)
db.update_table(table, pd.DataFrame(response.data))
```

## Package Structure

```
kactus_data/
├── schemas/
│   └── data_source.py  # SyncDataResponse model
├── sources/
│   ├── base.py         # DataSource ABC
│   └── mihong.py       # Mihong.vn gold price source
└── jobs/               # ETL job definitions (placeholder)
```

## Available Data Sources

| Source | Module | Description |
|--------|--------|-------------|
| Mihong.vn | `kactus_data.sources.mihong` | Vietnamese gold price data |

## Testing

```bash
uv run pytest packages/kactus-data/tests/ -v
```
