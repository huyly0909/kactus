---
name: model-registration
description: How to declare ORM models, register them via INSTALLED_PACKAGES, and ensure Alembic autogenerate discovers them
---

# ORM Model Registration

> **Related skills**: project-conventions, database-migration, feature-scaffold

This skill covers the convention that ensures every SQLAlchemy ORM model is visible to Alembic autogenerate across the kactus monorepo.

## Overview

```
┌─ Package __init__.py ─────────────┐
│  MODELS = ["pkg.feature.model"]   │ ← declares model modules
└───────────────────────────────────┘
              ▲
              │ imported by load_models()
              │
┌─ Settings (config.py) ────────────┐
│  INSTALLED_PACKAGES = [...]       │ ← lists packages to scan
└───────────────────────────────────┘
              ▲
              │ passed to load_models(settings)
              │
┌─ Alembic env.py ──────────────────┐
│  load_models(settings)            │ ← triggers model discovery
│  target_metadata = Base.metadata  │
└───────────────────────────────────┘
```

---

## 1. Declare Models in `__init__.py`

Every package that owns ORM models **must** expose a `MODELS` list in its top-level `__init__.py`:

```python
# packages/kactus-common/src/kactus_common/__init__.py

MODELS: list[str] = [
    "kactus_common.user.model",
    "kactus_common.project.model",
]
```

```python
# packages/kactus-fin/src/kactus_fin/__init__.py

MODELS: list[str] = [
    # "kactus_fin.billing.model",  ← add model module paths here
]
```

### Rules

- One `model.py` file per feature folder (e.g. `kactus_common/user/model.py`).
- All model classes must inherit from `Base` (from `kactus_common.database.oltp.models`).
- When you add a new feature with models, **append** the module path to `MODELS`.

---

## 2. Define `INSTALLED_PACKAGES` in Settings

Each package's settings class declares a `ClassVar[list[str]]` called `INSTALLED_PACKAGES`:

```python
# packages/kactus-common/src/kactus_common/config.py

class CommonSettings(BaseKactusSettings):
    INSTALLED_PACKAGES: ClassVar[list[str]] = ["kactus_common"]
```

Entry-point packages **must extend the parent's list**:

```python
# packages/kactus-fin/src/kactus_fin/config.py

class Settings(DataSettings):
    INSTALLED_PACKAGES: ClassVar[list[str]] = DataSettings.INSTALLED_PACKAGES + ["kactus_fin"]
```

### Rules

> [!CAUTION]
> Always **extend** the parent with `ParentSettings.INSTALLED_PACKAGES + [...]`.
> Overwriting it drops upstream models and Alembic will generate `DROP TABLE` migrations for those tables.

- Use `ClassVar[list[str]]` so Pydantic doesn't treat it as a settings field.
- Only add your own package name, not individual modules.

---

## 3. How `load_models()` Works

`load_models()` iterates `INSTALLED_PACKAGES`, imports each package, reads its `MODELS` attribute, and imports every listed module. This forces SQLAlchemy to register the model classes on `Base.metadata`.

It is called in Alembic `env.py` **before** setting `target_metadata`:

```python
# kactus_fin/migrations/env.py

from kactus_common.app_registry import load_models
from kactus_common.database.oltp.models import Base
from kactus_fin.config import get_settings

settings = get_settings()
load_models(settings)
target_metadata = Base.metadata
```

---

## Checklist: Adding a New Model

1. **Create the model file** in your feature folder
2. **Write the model class** inheriting from `Base` and appropriate mixins
3. **Register the module** in the package's `__init__.py` → `MODELS` list
4. **Verify `INSTALLED_PACKAGES`** in the entry-point settings includes your package
5. **Generate the migration**: `python manage.py fin db migrate -m "add table"`
6. **Review** the generated migration file, then apply: `python manage.py fin db upgrade`
