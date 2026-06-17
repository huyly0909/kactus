---
name: scaffold-feature
description: Generate boilerplate for a new feature (model, schema, API, service) in any usonia package
---

# Scaffold a new feature

Create the feature folder at `packages/<package>/src/<python_name>/$ARGUMENTS/` with these files:

## 1. `model.py`

```python
from sqlalchemy.orm import Mapped, mapped_column
from usonia_common.database.oltp.models import Base, ModelMixin, AuditMixin

class <Name>(Base, ModelMixin, AuditMixin):
    __tablename__ = "<table_name>"
    # add columns
```

After creating, register in the package's `__init__.py` MODELS list.

## 2. `schema.py`

```python
from usonia_common.schemas import BaseSchema, FancyInt

class <Name>Schema(BaseSchema):
    id: FancyInt
    # add fields

class Create<Name>Request(BaseSchema):
    # add fields
```

## 3. `service.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession

class <Name>Service:
    @staticmethod
    async def create(session: AsyncSession, ...) -> <Name>:
        ...
```

## 4. `api.py`

```python
from usonia_common.router import UsoniaAPIRouter
router = UsoniaAPIRouter(prefix="/<feature>", tags=["<feature>"])

@router.get("")
async def list_items() -> Pagination[<Name>Schema]:
    ...
```

## 5. Register in `app.py`

Include the new router in the package's app registration.

## 6. Generate migration

```bash
python manage.py sim db migrate -m "add <table_name> table"
python manage.py sim db upgrade
```

## 7. Write tests

Create `tests/<feature>/test_<feature>_api.py` with async client fixtures.
