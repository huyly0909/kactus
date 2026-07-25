# Dev servers — one target per process. `uv run` resolves backend/.venv, so no
# manual activation is needed; bun runs the vite dev server with the /api proxy.

.PHONY: fin fin-gw fin-data fin-ui \
        precommit format format-be format-fe lint lint-be lint-fe

fin:            ## kactus-fin (control plane) — :17600, hot-reload
	cd backend && uv run python manage.py fin dev

fin-gw:         ## kactus-fin-gateway — :17601, hot-reload
	cd backend && uv run python manage.py fin-gw dev

fin-data:       ## kactus-data-server (data plane) — :17602, hot-reload
	cd backend && uv run python manage.py data-server dev

fin-ui:         ## frontend (vite) — :17630, proxy /api -> :17600
	cd frontend && bun run dev

# ---------------------------------------------------------------------------
# Format / lint. Backend formatters run through pre-commit so the versions are
# pinned in exactly one place (.pre-commit-config.yaml); frontend goes through
# the workspace scripts (prettier/eslint from frontend/node_modules).
# ---------------------------------------------------------------------------

precommit:      ## install pre-commit (if missing) + git hooks
	@command -v pre-commit >/dev/null 2>&1 || uv tool install pre-commit
	pre-commit install

format: precommit format-be format-fe   ## reformat code + imports (both sides)

format-be:      ## backend: isort + autoflake + black (write)
	-pre-commit run isort --all-files
	-pre-commit run autoflake --all-files
	-pre-commit run black --all-files

format-fe:      ## frontend: prettier --write + eslint --fix
	cd frontend && bun run format
	-cd frontend && bunx turbo run lint -- --fix

lint: lint-be lint-fe                   ## check only, no rewrites (both sides)

lint-be:        ## backend: flake8 + import-linter layer contract
	pre-commit run flake8 --all-files
	cd backend && uv run lint-imports

lint-fe:        ## frontend: prettier --check + eslint
	cd frontend && bun run format:check
	cd frontend && bun run lint
