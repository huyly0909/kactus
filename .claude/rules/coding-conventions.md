---
description: Core coding conventions for the Usonia monorepo
---

# Coding Conventions

## Import Rules

All imports MUST be at the top of the file. The **only** exception is breaking a genuine circular import — in that case, an inline import inside the function is allowed, and the reason should be clear from context (or a one-line comment).

```python
# Correct
from usonia_common.database.oltp.session import get_db
from usonia_common.exceptions import NotFoundException
from usonia_common.schemas import BaseSchema

# Wrong — relative imports across packages
from ..usonia_common import NotFoundException

# Wrong — lazy import for no reason
def do_thing():
    from usonia_common.schemas import BaseSchema  # no circular import here
    ...

# Allowed — only to break a real circular import
def do_thing():
    from usonia_ai.chat.workflow_v1.graph import ChatWorkflowV1Graph  # circular: graph imports this module
    ...
```

## Typing — Python 3.12+

```python
# Correct
def process(items: list[str], config: dict[str, int] | None = None) -> str | None: ...

# Wrong — don't use typing.Dict, typing.List, typing.Union, typing.Optional
```

## Schemas (Pydantic)

All Pydantic schemas inherit from `BaseSchema` (never `BaseModel` directly):

```python
from usonia_common.schemas import BaseSchema, FancyInt, FancyFloat

class UserSchema(BaseSchema):
    id: FancyInt       # serialises int -> str in JSON
    name: str
    balance: FancyFloat
    email: str | None = None
```

Use `FancyInt` / `FancyFloat` for numeric fields to avoid JavaScript precision loss.

## OLTP Models (SQLAlchemy)

```python
from usonia_common.database.oltp.models import Base, ModelMixin, AuditMixin, LogicalDeleteMixin

class User(Base, ModelMixin, AuditMixin, LogicalDeleteMixin):
    __tablename__ = "users"
    name: Mapped[str] = mapped_column()
    email: Mapped[str | None] = mapped_column(default=None)
```

- `ModelMixin` -> snowflake `id`, `create_time`, `update_time`
- `AuditMixin` -> `created_by`, `updated_by` (auto-populated from ContextVar)
- `LogicalDeleteMixin` -> soft-delete via `deleted_timestamp`

## Service Pattern

```python
class MyService:
    @staticmethod
    async def list_items(session: AsyncSession) -> list[Item]:
        ...
```

## Logging — Loguru Only

```python
from loguru import logger
logger.info("Processing item {item_id}", item_id=42)
```

Never use `import logging` / `logging.getLogger(__name__)`.

## Adding Dependencies

Always use `uv add` to add a new Python library. Never hand-edit `pyproject.toml` dependency lists and never `pip install` into the venv.

```bash
# Correct — adds to pyproject.toml and updates uv.lock
uv add httpx
uv add --dev pytest-mock                 # dev dependency
uv add --package usonia-simulators boto3 # target a specific workspace package
```

## Don't Do This

- Import inside functions/methods (except to break a real circular import)
- Hand-edit `pyproject.toml` dependencies (use `uv add`)
- Use `pip install` inside the workspace (use `uv add`)
- Use `Union[A, B]`, `Optional[X]`, `Dict`, `List`
- Return raw dicts from API endpoints
- Use `int`/`float` in API schemas (use `FancyInt`/`FancyFloat`)
- Inherit from `BaseModel` directly
- Import app-specific code into `usonia-common`
- Create circular dependencies between packages
- Put business logic in `usonia-common` (infrastructure only)
- Add `__init__.py` to test directories
- Raise bare `Exception`
- Use `import logging`
- Manually set `created_by`/`updated_by`
- Use `fastapi.APIRouter` (use `UsoniaAPIRouter`)
- Skip tests
