---
description: ORM model registration for Alembic autogenerate
paths:
  - "**/__init__.py"
  - "**/model.py"
  - "**/config.py"
---

# ORM Model Registration

```
Package __init__.py:  MODELS = ["pkg.feature.model"]
         ↓ imported by load_models()
Settings config.py:   INSTALLED_PACKAGES = [...]
         ↓ passed to load_models(settings)
Alembic env.py:       load_models(settings) → target_metadata = Base.metadata
```

## 1. Declare Models in `__init__.py`

```python
# packages/usonia-simulators/src/usonia_simulators/__init__.py
MODELS: list[str] = [
    "usonia_simulators.energy_plus.file.model",
    "usonia_simulators.energy_plus.task.model",
    # one entry per model module
]
```

## 2. Extend INSTALLED_PACKAGES

```python
# packages/usonia-simulators/src/usonia_simulators/config.py
class Settings(CommonSettings):
    INSTALLED_PACKAGES: ClassVar[list[str]] = CommonSettings.INSTALLED_PACKAGES + ["usonia_simulators"]
```

Always **extend** the parent list. Overwriting drops upstream models and Alembic will generate DROP TABLE migrations.

## Checklist: Adding a New Model

1. Create `model.py` in feature folder
2. Write model class inheriting from `Base` + mixins
3. Register module in package `MODELS` list
4. Verify `INSTALLED_PACKAGES` includes your package
5. Generate migration: `python manage.py sim db migrate -m "add table"`
6. Review + apply: `python manage.py sim db upgrade`
