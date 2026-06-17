# Docker Conventions

## Directory Structure

- Dockerfiles go in `docker-hub/dockerfiles/` named `{service}.Dockerfile`
- Static build configs go in `docker-hub/config/` (nginx, supervisord, s6-overlay, entrypoints)
- Runtime scripts go in `docker-hub/scripts/`
- Compose lives in `docker-hub/dev/` (hot-reload, bind-mount source) and `docker-hub/prod/` (release-image, baked source). Both reuse the same Dockerfiles.
- Env-file *templates* live in `docker-hub/env_vars/*.example`. Each environment's actual `.env.*` files are symlinks/copies of those templates and stay alongside the compose file.

## URL & service-name conventions

See `.claude/rules/service-urls.md`. **Pydantic defaults and Dockerfile `ENV` directives MUST use `localhost` / `127.0.0.1`** (kuber-prod safe). Container names like `uso-simulators` are local-compose-only and live in `docker-hub/env_vars/*.example` overrides + `container_name:` declarations in the compose files.

## DSS Scripts

All DSS lifecycle scripts are in `docker-hub/scripts/dss/` and run inside code-server as abc user:

| Script | Purpose |
|--------|---------|
| `install.sh [base\|apps\|all]` | Install half — venv + pyradiance compile (`base`) + editable package installs (`apps`). **Baked at image build time** (code-server.Dockerfile); no DSS_API_KEY, starts nothing |
| `start.sh` | Start half — (re)spawn DSS server + workers. Runs on every boot via s6-overlay `init-usonia` (fast; no installing) |
| `setup.sh` | Manual full reinstall: thin wrapper = `install.sh all && start.sh` |
| `restart.sh` | Back-compat shim → `start.sh` |
| `stop.sh` | Stop DSS processes |
| `status.sh` | Check process status |
| `verify.sh` | Comprehensive environment check (incl. the `.baked` marker) |

Boot is fast because the venv (incl. the slow pyradiance C++ compile) and all
package installs are **baked into the image** under **`/opt/.usonia`** (`USONIA_HOME`,
NOT `/config` — so a persistent `/config` volume mount can't shadow them);
`init-usonia` only runs `start.sh`. It self-heals (runs `install.sh all` once) if
the baked venv/`.baked` marker is missing. In **dev**, source `.py` edits hot-reload
via the editable venv + the `../../packages` bind-mount onto `/opt/.usonia/packages`;
after adding a NEW Python dependency, run
`docker exec -u abc uso-code-server bash /opt/.usonia/docker-hub/scripts/dss/install.sh apps`
(seconds) or rebuild — or set `USONIA_REINSTALL_ON_BOOT=1` to reinstall every boot.

## Simulator Init Scripts

Per-simulator init scripts are in `docker-hub/scripts/init/simulators/`. They are idempotent — skip if assets are already baked into the image.

## Adding a New Service

1. Create `docker-hub/dockerfiles/{name}.Dockerfile`
2. Add service to `docker-hub/prod/docker-compose.yml`
3. Add env file to `docker-hub/prod/.env.{name}` if needed
4. Add config files to `docker-hub/config/` if Dockerfile needs COPY

## Don't Do This

- Put Dockerfiles at docker-hub root (use `dockerfiles/`)
- Mix operational scripts into `prod/` (use `scripts/`)
- Create separate setup scripts that call each other (merge into one)
- Put test scripts in `scripts/` (use pytest integration tests)
