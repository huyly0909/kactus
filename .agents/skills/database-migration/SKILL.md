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

## `migrations/env.py` Pattern

Each package's `env.py` must call `load_models(settings)` **before** setting
`target_metadata` so autogenerate can detect all ORM models
(see **model-registration** skill for the full convention):

```python
from kactus_common.app_registry import load_models
from kactus_common.database.oltp.models import Base
from <package>.config import get_settings

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Load all ORM models declared by installed packages
load_models(settings)

target_metadata = Base.metadata
```

> [!CAUTION]
> Never remove the `load_models(settings)` call. Without it `Base.metadata` is
> empty and autogenerate will produce `pass`-only migrations.

## Migration File Naming

Migration files use a date-prefixed format configured in `alembic.ini`:

```ini
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d%%(second).2d_%%(rev)s_%%(slug)s
```

This produces filenames like `20260224_222830_037b1163582d_add_users_and_sessions.py`, which sort chronologically and include the revision hash + message slug.

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
