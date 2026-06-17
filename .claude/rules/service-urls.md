---
description: Service URL conventions for local Docker vs production Kubernetes
paths:
  - "**/config.py"
  - "**/configs.py"
  - "**/settings.py"
  - "docker-hub/**"
---

# Service URL Conventions

This codebase ships to two very different runtimes:

| | Local (developer machine) | Production |
|---|---|---|
| Orchestrator | Docker Compose (`docker-hub/dev/`, `docker-hub/prod/`) | Kubernetes |
| Service names | Known — defined by `container_name:` in this repo | Unknown — assigned by DevOps in their cluster manifests, not in this repo |
| Inter-service host | Container DNS (`uso-simulators`, `uso-code-server`, `langfuse-web`, …) | `localhost` / `127.0.0.1` (sidecar / single-pod pattern) |

The convention: **code is K8s-default; Docker compose overrides via env files**. The motivation is that production is the harder case (we don't control or even know the deployed service names), so the safe default has to be the one that works there.

## Code defaults = localhost (production-safe)

Every Pydantic `BaseSettings` field that holds an inter-service URL **MUST default to `localhost`** (or `127.0.0.1`). Likewise every `ENV` directive in `docker-hub/dockerfiles/*.Dockerfile`. The reason: these defaults are what runs in K8s when no override is supplied, and DevOps shouldn't have to overwrite the Dockerfile/code just to deploy.

```python
# RIGHT — kuber-safe default
class SimulatorsSettings(BaseSettings):
    api_url: str = "http://localhost:5002"

# WRONG — bakes in a name only this repo's compose file knows
class SimulatorsSettings(BaseSettings):
    api_url: str = "http://uso-simulators:5002"
```

```dockerfile
# RIGHT — kuber-safe default
ENV SIMULATORS_API_URL http://127.0.0.1:5002
ENV CODE_SERVER_HOST   127.0.0.1

# WRONG — only resolves under this repo's compose
ENV SIMULATORS_API_URL http://uso-simulators:5002
```

This includes the code-server `EXEC_API` URL, the simulators API URL, langfuse base URL, postgres / chromadb hosts, and any URL one service uses to talk to another.

## Local Docker = override via env files

`docker-hub/dev/docker-compose.yml` and `docker-hub/prod/docker-compose.yml` each set `container_name:` for every service, so the names are predictable inside the compose network. Those names are the only place container names are allowed to be hardcoded.

Compose passes the container-name overrides through env files in `docker-hub/env_vars/*.example` (copied to `.env.*` per environment). Example for the AI service:

```env
# docker-hub/env_vars/env.ai.example  — compose-only overrides
SIMULATORS_API_URL=http://uso-simulators:5002
CODE_SERVER_HOST=uso-code-server
DATABASE_URL=postgresql://usonia:usonia@uso-postgres:5432/usonia
LANGFUSE_BASE_URL=http://langfuse-web:3000
```

Each `*.example` MUST carry a header comment explaining "Dockerfile bakes K8s-prod defaults; this file overrides for compose".

## Where container names ARE allowed

- `container_name:` in `docker-hub/{dev,prod}/docker-compose.yml`
- `*.env*` files in `docker-hub/env_vars/` (overrides for compose)
- Docs / chat context that explicitly describe the local-docker topology (e.g. `general_chat_context.md` — mark such docs as "local docker layout" so the chatbot doesn't blindly recite container names in prod)
- Integration tests that target the compose network (mark with the `integration` pytest marker)

## Where container names are NOT allowed

- `packages/*/src/**/config.py` defaults — use `localhost`
- `docker-hub/dockerfiles/*.Dockerfile` `ENV` directives — use `127.0.0.1`
- Inline URLs in Python source code (build URLs from settings)
- Default URLs in prompt templates rendered for the LLM — substitute from settings via the template render context

## Adding a new service URL — checklist

1. Pydantic field defaults to `localhost` (or `127.0.0.1`).
2. Dockerfile ENV defaults to `127.0.0.1`.
3. `docker-hub/env_vars/env.<service>.example` adds an override line mapping to the container name.
4. Both `dev/docker-compose.yml` and `prod/docker-compose.yml` consume the env file via `env_file:`.
5. If the URL appears in a prompt template (e.g. `{code_server_host}`), wire it through the prompt render context so the LLM sees the runtime value, not a hardcoded compose name.
