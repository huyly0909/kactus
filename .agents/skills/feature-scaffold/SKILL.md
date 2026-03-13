---
name: feature-scaffold
description: Use when creating a new feature (model, schema, API, service) in any kactus package. Provides the step-by-step checklist and file templates.
---

# Feature Scaffolding Skill

## Decision: Where does the feature go?

| Feature type | Location |
|-------------|----------|
| Shared across multiple apps (user, auth) | `kactus-common/src/kactus_common/<feature>/` |
| App-specific (billing, dashboard) | `<app-package>/src/<app_import>/<feature>/` |

## File Structure

Create a folder with these files:

```
<feature>/
├── __init__.py      # (empty or re-exports)
├── const.py         # Enums, constants, Permission subclass
├── model.py         # SQLAlchemy ORM models
├── schema.py        # Pydantic schemas
├── service.py       # Business logic
├── app.py           # KactusApp declaration (app-specific features)
└── api.py           # FastAPI router (if feature has endpoints)
```

## Step-by-Step

### 1. `const.py` — Enums & Permissions

```python
from kactus_common.authorization.const import Permission, PermissionAct

class BillingPermission(Permission):
    billing = "billing"
```

### 2. `model.py` — Database Model

```python
from sqlalchemy.orm import Mapped, mapped_column
from kactus_common.database.oltp.models import Base, ModelMixin, AuditMixin

class Invoice(Base, ModelMixin, AuditMixin):
    __tablename__ = "invoices"

    amount: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(default="draft")
    user_id: Mapped[int] = mapped_column()
```

### 3. `schema.py` — Pydantic Schemas

```python
from kactus_common.schemas import BaseSchema, FancyInt, FancyFloat

class InvoiceSchema(BaseSchema):
    id: FancyInt
    amount: FancyFloat
    status: str

class CreateInvoiceRequest(BaseSchema):
    amount: float
    user_id: int
```

### 4. `service.py` — Business Logic

```python
from sqlalchemy.ext.asyncio import AsyncSession

class InvoiceService:
    @staticmethod
    async def create(session: AsyncSession, ...) -> Invoice:
        invoice = Invoice.init(...)
        session.add(invoice)
        await session.commit()
        await session.refresh(invoice)
        return invoice
```

### 5. `api.py` — Router

```python
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import Pagination

router = KactusAPIRouter(prefix="/api/invoices", tags=["invoices"])

@router.get("")
async def list_invoices(request: Request) -> Pagination[InvoiceSchema]:
    user = request.state.user  # NOT Depends
    ...
```

### 6. `app.py` — KactusApp Registration

```python
from kactus_common.app_registry import KactusApp
from kactus_common.authorization.const import PermissionAct
from kactus_common.project.const import DefaultRole
from .const import BillingPermission
from .api import router

billing_app = KactusApp(
    name="billing",
    session_routes=[router],
    permissions=[BillingPermission.billing],
    role_permissions={
        DefaultRole.OWNER: [(BillingPermission.billing, PermissionAct.manage)],
        DefaultRole.MANAGER: [(BillingPermission.billing, PermissionAct.write)],
        DefaultRole.MEMBER: [(BillingPermission.billing, PermissionAct.read)],
    },
)
```

### 7. Register in Main App

```python
# In the main app's startup (e.g. kactus_fin/app.py)
from kactus_fin.billing.app import billing_app
app_manager.register(billing_app)
```

### 8. Create Migration

```bash
python manage.py fin db migrate -m "add invoices table"
python manage.py fin db upgrade
```

### 9. Write Tests

See the **testing** skill for conventions and fixture patterns.
