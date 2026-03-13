---
name: database-migration
description: Use when adding, modifying, or deleting database tables or columns. Covers Alembic migration workflow and model creation checklist.
---

# Database Migration Skill

## Commands

All via the centralized `manage.py`:

```bash
# Generate migration from model changes
python manage.py fin db migrate -m "add invoices table"
python manage.py fin-gw db migrate -m "add tokens table"

# Apply migrations
python manage.py fin db upgrade          # upgrade to latest
python manage.py fin db downgrade <rev>  # rollback to revision

# Inspect
python manage.py fin db current          # current revision
python manage.py fin db history          # migration history
```

## Workflow

### 1. Define or modify the model

```python
from sqlalchemy.orm import Mapped, mapped_column
from kactus_common.database.oltp.models import Base, ModelMixin, AuditMixin, LogicalDeleteMixin

class Invoice(Base, ModelMixin, AuditMixin, LogicalDeleteMixin):
    __tablename__ = "invoices"

    amount: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(default="draft")
```

### 2. Generate migration

```bash
python manage.py fin db migrate -m "add invoices table"
```

### 3. Review the generated migration

- Check `upgrade()` and `downgrade()` functions
- Alembic auto-generates from model diffs, but some changes need manual edits:
  - Data migrations (backfilling columns)
  - Renaming columns/tables (Alembic detects as drop + create)
  - Complex index or constraint changes

### 4. Apply

```bash
python manage.py fin db upgrade
```

### 5. Test

```bash
uv run pytest packages/kactus-fin/tests
```

## Model Checklist

- [ ] Inherit from `Base` + needed mixins (`ModelMixin`, `AuditMixin`, `LogicalDeleteMixin`)
- [ ] Set `__tablename__` explicitly (or rely on `resolve_table_name`)
- [ ] Use `Mapped[T]` + `mapped_column()` for all columns
- [ ] Use custom types where appropriate (`PasswordHash`, `DateTimeTzAware`, `PydanticJSONDict`)
- [ ] Use `ForeignKey` for relationships
- [ ] Create corresponding Pydantic schema in `schema.py`

## Custom Column Types

| Type | Use For |
|------|---------|
| `UnsignedBigInt` | Snowflake IDs |
| `DateTimeTzAware` | Timezone-aware datetimes (auto UTC) |
| `PasswordHash` | Bcrypt-hashed passwords |
| `PydanticJSONDict` | Pydantic model ↔ JSON column |
| `PydanticJSONList` | List of Pydantic models ↔ JSON column |

All imported from `kactus_common.database.oltp.types`.

## Docker Deployment

After deploy, run migrations inside the container:

```bash
docker compose exec kactus-fin python manage.py fin db upgrade
docker compose exec kactus-fin-gw python manage.py fin-gw db upgrade
```
