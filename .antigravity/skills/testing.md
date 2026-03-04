---
name: testing
description: Use when writing, running, fixing, or debugging tests. Covers pytest conventions, fixture patterns, and test organization for the kactus monorepo.
---

# Testing Skill

## Framework

- **pytest** + **pytest-asyncio** for async tests
- **aiosqlite** for in-memory SQLite DB (no external DB required)
- **httpx** `AsyncClient` with `ASGITransport` for API integration tests

## Directory Layout

```
packages/<package>/tests/
├── test_<module>.py          # One file per module or class
├── <feature>/                # Subdirectory per feature area
│   ├── test_<module>.py
│   └── ...
└── (NO __init__.py!)         # Never add __init__.py in test dirs
```

## Running Tests

```bash
uv run pytest                                    # all packages
uv run pytest packages/kactus-fin/tests          # one package
uv run pytest packages/kactus-data/tests/sources # one feature
uv run pytest -k "test_login"                    # by name filter
uv run pytest -m "not slow"                      # exclude slow tests
```

## Fixture Pattern for DB Tests

```python
import pytest_asyncio
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager

TEST_DB_URL = "sqlite+aiosqlite://"

@pytest_asyncio.fixture(scope="module")
async def db():
    """In-memory SQLite for testing."""
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()
```

## Fixture Pattern for API Integration Tests

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from kactus_common.config import CommonSettings, register_settings, clear_settings
from kactus_common.database.oltp import session as session_mod
from kactus_common.user import auth as auth_mod

@pytest_asyncio.fixture(scope="module")
async def app(db):
    """Create a test app with overridden dependencies."""
    register_settings(CommonSettings())

    # Patch singletons to use test DB
    session_mod._db = db
    auth_mod._auth = None

    from kactus_fin.app import create_app
    _app = create_app()
    yield _app

    # Restore
    session_mod._db = None
    auth_mod._auth = None
    clear_settings()

@pytest_asyncio.fixture
async def client(app):
    """Async HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

## Cleanup Fixture

```python
@pytest_asyncio.fixture(autouse=True)
async def clean_tables(db):
    """Clean up data between tests (keep tables, delete rows)."""
    yield
    async with db.get_session() as session:
        await session.execute(MyModel.__table__.delete())
        await session.commit()
```

## Test Structure

```python
import pytest

@pytest.mark.asyncio
async def test_create_user_success(client, seed_user):
    """Short description of what is being tested."""
    # Arrange — setup already done via fixtures

    # Act
    resp = await client.post("/api/users", json={...})

    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0"
    assert body["data"]["email"] == "test@kactus.io"
```

## Checklist

1. **Write tests** for all new modules, functions, and API endpoints
2. **Update tests** when modifying existing code
3. **Run tests** before committing: `uv run pytest`
4. **Organise** by feature — one file per module in subdirectories
5. **No `__init__.py`** in test directories
6. **Use markers** for slow/integration tests: `@pytest.mark.slow`, `@pytest.mark.integration`
