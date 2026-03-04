# Production Release Checklist

## Pre-Release

- [ ] All tests pass: `pnpm test`
- [ ] Lint passes: `pnpm lint`
- [ ] Build succeeds: `pnpm build --filter bloom-app`
- [ ] Environment variables are set correctly in `.env` (prod)
  - `VITE_API_BASE_URL`
  - `VITE_WS_BASE_URL`
  - `VITE_APP_NAME`

## Build & Deploy

- [ ] Navigate to production Docker config:
  ```bash
  cd packages/docker-hub/prod
  ```
- [ ] Build and start containers:
  ```bash
  docker compose up -d --build
  ```
- [ ] Verify containers are healthy:
  ```bash
  docker compose ps
  ```

## Post-Deploy Verification

- [ ] Application loads at the production URL
- [ ] Login flow works (session cookie is set)
- [ ] Project selection and dashboard load correctly
- [ ] WebSocket connection establishes (if applicable)

## Known Dev-Only Behaviors

> [!NOTE]
> **React StrictMode** causes all API calls to fire twice in `development` mode only.
> This does NOT happen in production builds. Do not treat duplicate dev-mode requests as a bug.
