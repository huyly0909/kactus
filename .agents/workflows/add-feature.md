---
description: How to add a new feature folder to kactus-fin
---

# Adding a New Feature to kactus-fin

## Structure

Create a folder under `packages/kactus-fin/src/kactus_fin/<feature_name>/` with:

```
<feature_name>/
├── __init__.py      # empty
├── app.py           # KactusApp registration
├── api.py           # FastAPI routes (KactusAPIRouter)
├── schema.py        # Pydantic request/response models
└── service.py       # Business logic (staticmethod pattern)
```

## 1. `app.py` — Feature registration

```python
from kactus_common.app_registry import KactusApp
from kactus_fin.<feature_name>.api import router

<feature_name>_app = KactusApp(
    name="<feature_name>",
    superuser_routes=[router],  # or session_routes=[] for non-admin
)
```

## 2. `service.py` — Business logic (staticmethod pattern)

**Use `@staticmethod` for all methods.** Pass dependencies (e.g. `storage`, `session`) as the first argument. Do NOT use `__init__` / instance state.

```python
class MyService:
    @staticmethod
    def list_items(storage: DuckDBStorage) -> list[MyItem]:
        df = storage.query("SELECT ... FROM my_table")
        return [MyItem(**row) for row in df.to_dict("records")]

    @staticmethod
    def sync(storage: DuckDBStorage, code: str) -> SyncResult:
        source = MySource()
        pipeline = SyncPipeline(source=source, storage=storage)
        return pipeline.run(table=MY_TABLE, code=code, ...)
```

## 3. `api.py` — Routes

```python
from kactus_common.router import KactusAPIRouter
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_fin.config import get_settings

router = KactusAPIRouter(prefix="/api/<feature_name>", tags=["<feature_name>"])

def _get_storage() -> DuckDBStorage:
    settings = get_settings()
    return DuckDBStorage(db_path=settings.db_path)

@router.get("")
async def list_items(request: Request) -> Pagination[MyItem]:
    storage = _get_storage()
    items = MyService.list_items(storage)
    return Pagination(total=len(items), items=items)
```

## 4. `schema.py` — Pydantic models

```python
from pydantic import BaseModel

class MyItem(BaseModel):
    field: str
    ...
```

## 5. Register in `app.py` (root)

In `packages/kactus-fin/src/kactus_fin/app.py`:

```python
from kactus_fin.<feature_name>.app import <feature_name>_app
# ...
app_manager.register(<feature_name>_app)
```
