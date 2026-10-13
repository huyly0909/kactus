# Dev servers — one target per process. `uv run` resolves backend/.venv, so no
# manual activation is needed; bun runs the vite dev server with the /api proxy.

.PHONY: fin fin-gw fin-data fin-ui empty-db \
        precommit format format-be format-fe lint lint-be lint-fe

fin:            ## kactus-fin (control plane) — :17600, hot-reload
	cd backend && uv run python manage.py fin dev

fin-gw:         ## kactus-fin-gateway — :17601, hot-reload
	cd backend && uv run python manage.py fin-gw dev

fin-data:       ## kactus-data-plane (data plane) — :17602, hot-reload
	cd backend && uv run python manage.py data-plane dev

fin-ui:         ## frontend (vite) — :17630, proxy /api -> :17600
	cd frontend && bun run dev

# ---------------------------------------------------------------------------
# Database reset (dev only). Wipes BOTH stores and rebuilds from scratch:
#   - Postgres (dev compose): DROP SCHEMA public CASCADE, then alembic upgrade
#   - DuckDB: delete backend/kactus.duckdb (ETL recreates tables on next crawl)
# Aborts if any process (data plane, DBeaver) still holds the DuckDB file open.
# ---------------------------------------------------------------------------

DEV_COMPOSE := docker compose -f deploy/dev/docker-compose.yml
DUCKDB_FILE := backend/kactus.duckdb

empty-db:       ## DESTRUCTIVE: wipe Postgres + DuckDB, re-run migrations
	@printf 'This will ERASE all Postgres data and delete %s. Type "yes" to continue: ' "$(DUCKDB_FILE)"; \
	read ans; [ "$$ans" = "yes" ] || { echo "Aborted."; exit 1; }
	@if lsof -t "$(DUCKDB_FILE)" >/dev/null 2>&1; then \
		echo "ERROR: $(DUCKDB_FILE) is open (data plane or DBeaver?). Close it first:"; \
		lsof "$(DUCKDB_FILE)"; exit 1; \
	fi
	$(DEV_COMPOSE) exec -T postgres psql -U kactus -d kactus \
		-c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	cd backend && uv run python manage.py fin db upgrade
	rm -f $(DUCKDB_FILE) $(DUCKDB_FILE).wal
	@echo ""
	@echo "Done. Postgres is at migration head; DuckDB will be recreated on the next crawl."
	@echo "Recreate the admin user with:"
	@echo "  cd backend && uv run python manage.py fin user create-admin"

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
