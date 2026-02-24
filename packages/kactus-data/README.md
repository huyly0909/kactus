# kactus-data

Data ETL library for the Kactus monorepo. Fetches data from external sources, transforms it, and stores it in DuckDB. Designed to work standalone, in Airflow DAGs, or Celery tasks.

## Architecture

```
kactus_data/
├── sources/              # Data source connectors
│   ├── http.py           # HttpDataSource ABC (HTTP polling base)
│   ├── gold/mihong.py    # MihongGoldSource (mihong.vn)
│   ├── stock/            # Stock data sources (placeholder)
│   └── coin/             # Crypto data sources (placeholder)
├── storage/
│   └── duckdb.py         # DuckDBStorage — store, query, export
├── pipeline.py           # SyncPipeline: source → transform → storage
├── schemas.py            # SyncDataResponse, SyncResult
├── cli/                  # CLI commands (backup, sync)
└── jobs/                 # Airflow/Celery task definitions
```

## Quick Start

### As a library (Airflow / Celery / scripts)

```python
from datetime import date
from kactus_data.sources.gold import MihongGoldSource
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_data.pipeline import SyncPipeline
from kactus_common.database.duckdb.schema import Table, Column
from kactus_common.database.duckdb.consts import DataType

# Define source and storage
source = MihongGoldSource(xsrf_token="your-token")
storage = DuckDBStorage(db_path="kactus.duckdb")

# Define target table
table = Table(
    name="gold_prices",
    columns=[
        Column(name="code", data_type=DataType.STRING),
        Column(name="price", data_type=DataType.FLOAT),
        Column(name="date", data_type=DataType.DATE),
    ],
)

# Run the pipeline
pipeline = SyncPipeline(source, storage)
result = pipeline.run(
    table=table,
    code="SJC",
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31),
)

print(f"Fetched: {result.rows_fetched}, Stored: {result.rows_stored}")
```

### Via CLI

```bash
# Sync data from a source
python manage.py data sync gold mihong -c SJC -s 2024-01-01 -e 2024-01-31

# Backup
python manage.py data backup list                             # list tables
python manage.py data backup table gold_prices -o ./backups   # single table
python manage.py data backup all -o ./backups                 # all tables
python manage.py data backup table gold_prices -f csv         # CSV format
```

## Adding a New Data Source

1. Create a domain folder if it doesn't exist: `sources/<domain>/`
2. Subclass `HttpDataSource`:

```python
# sources/stock/vndirect.py
from kactus_data.sources.http import HttpDataSource
from kactus_data.schemas import SyncDataResponse

class VNDirectSource(HttpDataSource):
    def __init__(self, api_key: str):
        super().__init__("https://api.vndirect.com.vn", "vndirect")
        self.api_key = api_key

    def sync(self, start_date, end_date, code) -> SyncDataResponse:
        # Fetch and return data
        ...

    def _format_request_date(self, date_obj, is_end_date=False) -> str:
        return date_obj.strftime("%Y-%m-%d")

    def _get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _get_cookies(self) -> dict[str, str]:
        return {}
```

3. Register in `sources/<domain>/__init__.py`
4. Optionally register in `cli/sync.py` for CLI access

## Custom Transform

Pass a `transform` function to the pipeline to convert raw API responses into DataFrames:

```python
import pandas as pd

def transform_mihong(raw_data: dict) -> pd.DataFrame:
    records = raw_data.get("prices", [])
    df = pd.DataFrame(records)
    df["price"] = df["price"].astype(float)
    return df

result = pipeline.run(table=table, code="SJC", ..., transform=transform_mihong)
```

## Tests

```bash
uv run pytest packages/kactus-data/tests/ -v
```
