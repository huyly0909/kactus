---
name: add-feature
description: Step-by-step workflow for adding a new feature to a Usonia package
---

# Adding a New Feature

## Where does it go?

| Feature type | Location |
|-------------|----------|
| Shared across packages | `usonia-common/src/usonia_common/<feature>/` |
| Simulator-specific | `usonia-simulators/src/usonia_simulators/<feature>/` |
| AI/Orchestrator | `usonia-ai/src/usonia_ai/<feature>/` |

## Steps

1. **Create folder structure** — `model.py`, `schema.py`, `service.py`, `api.py`, `__init__.py`
2. **Write the model** — inherit from `Base`, `ModelMixin`, `AuditMixin`
3. **Register the model** — add to package's `MODELS` list in `__init__.py`
4. **Write schemas** — inherit from `BaseSchema`, use `FancyInt`/`FancyFloat`
5. **Write service** — `@staticmethod` pattern, pass `session` as first arg
6. **Write routes** — use `UsoniaAPIRouter`, return plain data objects
7. **Register router** — include in `app.py`
8. **Generate migration** — `python manage.py sim db migrate -m "description"`
9. **Apply migration** — `python manage.py sim db upgrade`
10. **Write tests** — async fixtures, test all endpoints
11. **Run tests** — `uv run pytest`

Use `/scaffold-feature <name>` to generate the boilerplate files.
