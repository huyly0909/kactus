---
name: coding-conventions
description: Core coding conventions and import rules for the Kactus monorepo. Use on every task involving code changes.
---

# Kactus Monorepo — Coding Conventions

> **Related skills**: project-conventions, api-conventions, database-migration, feature-scaffold, model-registration, testing

## Import Rules

**All imports MUST be at the top of the file — never inside functions or methods.**

```python
# ✅ Correct — imports at top of file
from kactus_common.exceptions import NotFoundError
from kactus_common.schemas import BaseSchema

# ❌ Wrong — import inside function
class MyService:
    @staticmethod
    async def get_item(item_id: int) -> Item:
        from kactus_common.exceptions import NotFoundError  # NEVER do this
        ...
```

## Full Package Paths

```python
# ✅ Correct
from kactus_common.database.oltp.session import get_db
from kactus_common.exceptions import NotFoundError
from kactus_common.schemas import BaseSchema

# ❌ Wrong — relative imports across packages
from ..kactus_common import NotFoundError
```

## Typing — Modern Python 3.12+

```python
# ✅ Correct
def process(items: list[str], config: dict[str, int] | None = None) -> str | None: ...

# ❌ Wrong — don't use typing.Dict, typing.List, typing.Union, typing.Optional
```

## Schemas (Pydantic)

All Pydantic schemas **must** inherit from `BaseSchema`:

```python
from kactus_common.schemas import BaseSchema, FancyInt, FancyFloat

class UserSchema(BaseSchema):
    id: FancyInt                    # serialises int → str in JSON
    name: str
    balance: FancyFloat             # serialises float → str in JSON
    email: str | None = None
```

`BaseSchema` provides: whitespace stripping, empty-string-to-None conversion, `from_attributes=True` for ORM loading.

**API responses** must always use Pydantic schemas — never return raw dicts. Use `FancyInt` / `FancyFloat` for numeric fields to avoid JavaScript precision loss.

## OLTP Models (SQLAlchemy)

```python
from kactus_common.database.oltp.models import Base, ModelMixin, AuditMixin, LogicalDeleteMixin

class User(Base, ModelMixin, AuditMixin, LogicalDeleteMixin):
    __tablename__ = "users"
    name: Mapped[str] = mapped_column()
    email: Mapped[str | None] = mapped_column(default=None)
```

- `ModelMixin` → snowflake `id`, `create_time`, `update_time`
- `AuditMixin` → `created_by`, `updated_by` (auto-populated from ContextVar, do NOT set manually)
- `AuditCreatorMixin` → `created_by` only
- `LogicalDeleteMixin` → soft-delete via `deleted_timestamp`

> Custom column types (`PasswordHash`, `DateTimeTzAware`, etc.) — see **database-migration** skill

## Database Access — `get_db()` Singleton

```python
from kactus_common.database.oltp.session import get_db

async with get_db().get_session() as session:
    user = await User.get_or_404(session, user_id)
```

> Endpoint DB patterns (`provide_session`, etc.) — see **api-conventions** skill

## Service Pattern — Staticmethod

```python
class MyService:
    @staticmethod
    async def list_items(session: AsyncSession) -> list[Item]:
        ...

    @staticmethod
    async def get_item(session: AsyncSession, item_id: int) -> Item:
        ...
```

## Exception Pattern

```python
from kactus_common.exceptions import NotFoundError, DatabaseError

raise NotFoundError("User not found", tip="Check the user ID", data={"user_id": user_id})
```

For **package-specific** exceptions, subclass `KactusException` — caught by the FastAPI handler automatically.

## Logging — Loguru Only

```python
from loguru import logger

logger.info("Processing item {item_id}", item_id=42)
```

❌ Never use `import logging` / `logging.getLogger(__name__)`.

## Don't Do This

- ❌ Import inside functions/methods — always at top of file
- ❌ Use `Union[A, B]`, `Optional[X]`, `Dict`, `List` — use `A | B`, `X | None`, `dict`, `list`
- ❌ Return raw dicts from API endpoints — always use Pydantic schemas
- ❌ Use `int` / `float` in API schemas — use `FancyInt` / `FancyFloat`
- ❌ Use `.value` on `StrEnum` / `IntEnum` — they are already `str` / `int`
- ❌ Inherit from `BaseModel` directly — use `BaseSchema` from `kactus_common.schemas`
- ❌ Import app-specific code into `kactus-common`
- ❌ Create circular dependencies between packages
- ❌ Put business logic in `kactus-common` (infrastructure only)
- ❌ Write duplicate utilities — check `kactus-common` first
- ❌ Add `__init__.py` to test directories
- ❌ Raise bare `Exception` — use `KactusException` subclasses
- ❌ Use `import logging` / `logging.getLogger(__name__)` — use `from loguru import logger`
- ❌ Manually set `created_by` / `updated_by` — `AuditMixin` auto-populates from ContextVar
- ❌ Use `fastapi.APIRouter` — use `KactusAPIRouter` from `kactus_common.router`
- ❌ Skip tests — every feature needs tests
