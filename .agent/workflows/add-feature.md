---
description: How to add a new feature to a Kactus package
---

# Adding a New Feature

> **Related skills**: feature-scaffold, database-migration, testing, api-conventions, model-registration

## Structure

Create a folder under `packages/<package>/src/<python_name>/<feature_name>/` with:

```
<feature_name>/
├── __init__.py      # empty
├── const.py         # Enums, constants, Permission subclass
├── model.py         # SQLAlchemy ORM models (if feature has DB tables)
├── api.py           # FastAPI routes (KactusAPIRouter)
├── schema.py        # Pydantic request/response models
├── service.py       # Business logic (staticmethod pattern)
└── app.py           # KactusApp declaration (app-specific features)
```

## 1. `service.py` — Business logic (staticmethod pattern)

**Use `@staticmethod` for all methods.** Pass dependencies (e.g. `session`) as the first argument.

```python
from sqlalchemy.ext.asyncio import AsyncSession

from kactus_common.exceptions import NotFoundError

class MyService:
    @staticmethod
    async def list_items(session: AsyncSession) -> list[MyItem]:
        ...

    @staticmethod
    async def get_item(session: AsyncSession, item_id: int) -> MyItem:
        ...
```

## 2. `api.py` — Routes

```python
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import Pagination, FancyInt

from .schema import MyItemResponse
from .service import MyService

router = KactusAPIRouter(prefix="/api/<feature_name>", tags=["<feature_name>"])

@router.get("")
async def list_items(request: Request) -> Pagination[MyItemResponse]:
    ...

@router.get("/{item_id}")
async def get_item(item_id: FancyInt) -> MyItemResponse:
    ...
```

## 3. `schema.py` — Pydantic models

```python
from kactus_common.schemas import BaseSchema, FancyInt

class MyItemResponse(BaseSchema):
    id: FancyInt
    name: str
```

## 4. `model.py` — Database model (if needed)

```python
from sqlalchemy.orm import Mapped, mapped_column
from kactus_common.database.oltp.models import Base, ModelMixin, AuditMixin

class MyItem(Base, ModelMixin, AuditMixin):
    __tablename__ = "my_items"
    name: Mapped[str] = mapped_column()
```

> [!IMPORTANT]
> After creating `model.py`, register it in the package's `MODELS` list
> (see **model-registration** skill):
> ```python
> # packages/<pkg>/src/<pkg_name>/__init__.py
> MODELS: list[str] = [
>     ...,
>     "<pkg_name>.<feature>.model",  # ← add this
> ]
> ```

## 5. `app.py` — KactusApp Registration

```python
from kactus_common.app_registry import KactusApp
from kactus_common.authorization.const import PermissionAct
from kactus_common.project.const import DefaultRole
from .const import MyPermission
from .api import router

my_app = KactusApp(
    name="my_feature",
    session_routes=[router],
    permissions=[MyPermission.my_feature],
    role_permissions={
        DefaultRole.OWNER: [(MyPermission.my_feature, PermissionAct.manage)],
        DefaultRole.MANAGER: [(MyPermission.my_feature, PermissionAct.write)],
        DefaultRole.MEMBER: [(MyPermission.my_feature, PermissionAct.read)],
    },
)
```

## 6. Register in Main App

```python
# In the main app's startup (e.g. kactus_fin/app.py)
from kactus_fin.my_feature.app import my_app
app_manager.register(my_app)
```

## 7. Create Migration (if model added)

```bash
python manage.py fin db migrate -m "add my_items table"
python manage.py fin db upgrade
```

## 8. Write Tests

See the **testing** skill for conventions and fixture patterns.

```bash
uv run pytest packages/<package>/tests
```
