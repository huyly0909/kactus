---
name: model-registration
description: How to declare ORM models, register them via INSTALLED_PACKAGES, and ensure Alembic autogenerate discovers them
---

# ORM Model Registration

This skill covers the three-part convention that ensures every SQLAlchemy ORM
model is visible to Alembic autogenerate across the kactus monorepo.

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

Every package that owns ORM models **must** expose a `MODELS` list in its
top-level `__init__.py`. Each entry is a dotted import path to a module
containing SQLAlchemy model classes.

```python
# packages/kactus-common/src/kactus_common/__init__.py

MODELS: list[str] = [
    "kactus_common.user.model",
    "kactus_common.project.model",
]
```

```python
# packages/kactus-fin/src/kactus_fin/__init__.py

MODELS: list[str] = []  # add entries when you create models in kactus-fin
```

### Rules

- One `model.py` file per feature folder (e.g. `kactus_common/user/model.py`).
- All model classes in that file must inherit from `Base` (from
  `kactus_common.database.oltp.models`).
- When you add a new feature with models, **append** the module path to `MODELS`.

---

## 2. Define `INSTALLED_PACKAGES` in Settings

Each package's settings class declares a `ClassVar[list[str]]` called
`INSTALLED_PACKAGES`. This lists every package whose models should be loaded.

### Base (kactus-common)

```python
# packages/kactus-common/src/kactus_common/config.py

class CommonSettings(BaseKactusSettings):
    INSTALLED_PACKAGES: ClassVar[list[str]] = ["kactus_common"]
```

### Mid-level (kactus-data)

`kactus-data` has no ORM models, so it inherits without extending:

```python
# packages/kactus-data/src/kactus_data/config.py

class DataSettings(CommonSettings):
    # No INSTALLED_PACKAGES override — inherits ["kactus_common"]
    ...
```

### Leaf / entry-point (kactus-fin)

**Must extend the parent's list** so that all upstream models are included:

```python
# packages/kactus-fin/src/kactus_fin/config.py

from typing import ClassVar
from kactus_data.config import DataSettings

class Settings(DataSettings):
    INSTALLED_PACKAGES: ClassVar[list[str]] = DataSettings.INSTALLED_PACKAGES + ["kactus_fin"]
```

### Rules

> [!CAUTION]
> Always **extend** the parent with `ParentSettings.INSTALLED_PACKAGES + [...]`.
> Overwriting it drops upstream models and Alembic will generate `DROP TABLE`
> migrations for those tables.

- Use `ClassVar[list[str]]` so Pydantic doesn't treat it as a settings field.
- Only add your own package name (e.g. `"kactus_fin"`), not individual modules.
- The inheritance chain determines the final list at runtime:
  ```
  CommonSettings  → ["kactus_common"]
  DataSettings    → ["kactus_common"]           (inherited, no models in kactus-data)
  fin Settings    → ["kactus_common", "kactus_fin"]
  ```

---

## 3. How `load_models()` Works

`load_models()` in `kactus_common.app_registry` iterates `INSTALLED_PACKAGES`,
imports each package, reads its `MODELS` attribute, and imports every listed
module. This forces SQLAlchemy to register the model classes on `Base.metadata`.

```python
# kactus_common/app_registry.py

def load_models(settings) -> None:
    import importlib

    for pkg_name in settings.INSTALLED_PACKAGES:
        pkg = importlib.import_module(pkg_name)
        for module_path in getattr(pkg, "MODELS", []):
            importlib.import_module(module_path)
```

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

1. **Create the model file** in your feature folder:
   ```
   packages/<pkg>/src/<pkg_name>/<feature>/model.py
   ```

2. **Write the model class** inheriting from `Base` and appropriate mixins:
   ```python
   from kactus_common.database.oltp.models import Base, ModelMixin, AuditMixin

   class MyModel(Base, ModelMixin, AuditMixin):
       __tablename__ = "my_models"
       ...
   ```

3. **Register the module** in the package's `__init__.py`:
   ```python
   MODELS: list[str] = [
       ...,
       "<pkg_name>.<feature>.model",  # ← add this
   ]
   ```

4. **Verify `INSTALLED_PACKAGES`** in the entry-point settings includes your
   package. If your package is new, add it:
   ```python
   INSTALLED_PACKAGES: ClassVar[list[str]] = ParentSettings.INSTALLED_PACKAGES + ["<pkg_name>"]
   ```

5. **Generate the migration**:
   ```bash
   cd packages/<entry-point-pkg>
   uv run alembic revision --autogenerate -m "add my_models table"
   ```

6. **Review** the generated migration file, then apply:
   ```bash
   uv run alembic upgrade head
   ```
