---
description: Alembic migration workflow and model conventions
paths:
  - "**/migrations/**"
  - "**/model.py"
  - "manage.py"
---

# Database Migrations

## Commands

```bash
python manage.py sim db migrate -m "add invoices table"
python manage.py sim db upgrade
python manage.py sim db downgrade <rev>
python manage.py sim db current
python manage.py sim db history

python manage.py ai db migrate -m "add users table"
python manage.py ai db upgrade
```

## Workflow

1. Define/modify the model in `model.py`
2. Generate: `python manage.py sim db migrate -m "description"`
3. Review the generated migration (check upgrade + downgrade)
4. Apply: `python manage.py sim db upgrade`
5. Test: `uv run pytest`

## Model Pattern

```python
from sqlalchemy.orm import Mapped, mapped_column
from usonia_common.database.oltp.models import Base, ModelMixin, AuditMixin, LogicalDeleteMixin

class Invoice(Base, ModelMixin, AuditMixin, LogicalDeleteMixin):
    __tablename__ = "invoices"
    amount: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(default="draft")
```

## Custom Column Types

| Type | Use For |
|------|---------|
| `DateTimeTzAware` | Timezone-aware datetimes (auto UTC) |
| `CompressedJSONType` | Compressed JSON blob storage |
| `PydanticJSONDict` | Pydantic model <-> JSON column |
| `PydanticJSONList` | List of Pydantic models <-> JSON column |

All from `usonia_common.database.oltp.types`.

## Model Checklist

- Inherit from `Base` + mixins (`ModelMixin`, `AuditMixin`, `LogicalDeleteMixin`)
- Set `__tablename__` explicitly
- Use `Mapped[T]` + `mapped_column()` for all columns
- Create corresponding Pydantic schema in `schema.py`
- Register in package `MODELS` list (see model-registration rule)
