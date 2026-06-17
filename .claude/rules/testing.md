---
description: Testing conventions and fixture patterns for Usonia
paths:
  - "**/test_*.py"
  - "**/tests/**"
  - "**/conftest.py"
---

# Testing Conventions

## Framework

- **pytest** + **pytest-asyncio** for async tests
- **aiosqlite** for in-memory SQLite DB
- **httpx** `AsyncClient` with `ASGITransport` for API tests (unit), real HTTP client (integration)

## Running Tests

```bash
uv run pytest                                           # unit tests only (fast, ~3s)
uv run pytest packages/usonia-simulators/tests          # one package
uv run pytest -k "test_login"                           # by name

# Integration tests (requires running Docker containers)
uv run pytest packages/usonia-simulators/tests/integration/ -m integration
uv run pytest packages/usonia-simulators/tests/integration/ -m "integration and sap10"
uv run pytest packages/usonia-simulators/tests/integration/ -m "integration and not slow"
```

## Test Markers (REQUIRED)

Every test file MUST declare markers via `pytestmark` at the module level. Tests without markers will not be categorized correctly.

### Available Markers

| Marker | Purpose | Where |
|--------|---------|-------|
| `integration` | Real API tests (requires Docker containers) | `tests/integration/` only |
| `slow` | Long-running tests (>30s) | radiance, phpp, sbem, parallel |
| `uvalue` | U-Value simulator | feature tag |
| `sap10` | SAP10 simulator | feature tag |
| `hem` | HEM simulator | feature tag |
| `energyplus` | EnergyPlus simulator | feature tag |
| `radiance` | Radiance simulator | feature tag |
| `phpp` | PHPP simulator | feature tag |
| `sbem` | SBEM simulator | feature tag |

### How to Apply Markers

```python
# Integration test — MUST have `integration` + feature marker
pytestmark = [pytest.mark.integration, pytest.mark.sap10]

# Integration + slow
pytestmark = [pytest.mark.integration, pytest.mark.radiance, pytest.mark.slow]
```

Unit tests (in-memory DB, no Docker) do NOT need markers — they run by default.

### Test Separation

| Directory | Default run | Markers needed |
|-----------|-------------|----------------|
| `tests/` (any non-integration) | `uv run pytest` | None (runs by default) |
| `tests/integration/` | Excluded by default | `integration` + feature tag |

Integration tests live in `packages/usonia-simulators/tests/integration/` and are **excluded from the default `uv run pytest` run**. They must be invoked explicitly.

## DB Fixture (Unit Tests)

```python
TEST_DB_URL = "sqlite+aiosqlite://"

@pytest_asyncio.fixture(scope="session")
async def db():
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()
```

## API Client Fixture (Unit Tests)

```python
@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

## API Client Fixture (Integration Tests)

```python
@pytest_asyncio.fixture
async def api(_check_api_health):
    async with httpx.AsyncClient(base_url=SIMULATORS_API_URL, timeout=180) as client:
        yield client
```

## Test Structure

```python
import pytest

@pytest.mark.asyncio
async def test_create_item_success(client):
    # Arrange (fixtures)
    # Act
    resp = await client.post("/api/items", json={...})
    # Assert
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "test"
```

## Envelope assertions (every new API test)

Success and error responses use a single envelope shape — both directions
should be asserted explicitly:

```python
# Success (auto-wrapped by UsoniaAPIRouter)
assert resp.status_code == 200
body = resp.json()
assert body["code"] == "0"
assert body["msg"] == "success"
data = body["data"]            # the endpoint's typed payload

# Paginated list
assert data["page"] == 1
assert data["page_size"] == 20
assert "total" in data
assert "items" in data

# Task envelope (TaskEnvelope[<Sim>Result])
env = body["data"]
assert env["simulator"] == "sap10"
assert env["status"] in {"init", "in_progress", "success", "failed"}
assert env["run_type"] in {"sync", "async", "dss"}
# `result` populated when status == success; `error` populated when failed

# Error envelope (NotFoundException → 404, etc.)
assert resp.status_code == 404
body = resp.json()
assert body["code"] == "NOT_FOUND"
assert body["data"] is None
assert body["error"]["type"] == "NotFoundException"

# Validation error (RequestValidationError → 422)
assert resp.status_code == 422
assert resp.json()["code"] == "VALIDATION_ERROR"
```

Clone the SAP10 tests at `packages/usonia-simulators/tests/sap10/` as a
starting template for any new simulator's task + file test suite.

## Integration Test Pattern (3 modes)

Each simulator integration test MUST verify all 3 run modes with result comparison:

```python
pytestmark = [pytest.mark.integration, pytest.mark.sap10]

async def test_sap10_sync(api, _upload_file):
    """SYNC — immediate result, verify expected values."""

async def test_sap10_async(api, _upload_file):
    """ASYNC — poll until success, verify same result as SYNC."""

async def test_sap10_dss(api, _upload_file):
    """DSS — dispatched to worker, poll until success, verify same result."""

async def test_sap10_results_match_across_modes(api, _upload_file):
    """All 3 modes must produce identical output values."""
```

## Rules

- One test file per module in subdirectories
- No `__init__.py` in test directories
- Integration tests go in `tests/integration/` with `integration` marker
- Feature markers (`sap10`, `energyplus`, etc.) required on integration tests
- `slow` marker on tests >30s (radiance, phpp, sbem, parallel)
- `uv run pytest` must pass with 0 failures, 0 warnings, 0 deselected before committing
- Integration tests must test all 3 modes: sync, async, dss
- Integration tests must verify **actual result data matches** across modes, not just status
