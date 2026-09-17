# Test workspace

This directory is the root entry point for cross-module regression tests. Unit
tests stay beside the module they own; browser journeys, shared fixtures and
release-level orchestration live here.

## Layout

- `e2e/specs`: user-visible Playwright journeys.
- `e2e/pages`: page objects and stable UI operations.
- `e2e/fixtures`: Playwright fixtures, diagnostics and generated accounts.
- `e2e/support`: isolated API startup and test-runtime preparation.
- `api`: entry documentation for the full HTTP release acceptance suite.
- `fixtures`: reusable, non-sensitive test data.
- `mobile`: shared navigation, auth-gate, UI-safety and structure contracts for all mobile clients.
- `artifacts`: traces, screenshots, videos and reports; ignored by Git.

## Commands

```bash
npm run test:e2e
npm run test:e2e:headed
npm run test:e2e:ui
npm run test:regression
make mobile-check
```

The E2E suite starts its own API on `127.0.0.1:18020` and Vite server on
`127.0.0.1:15175`. It uses SQLite and local object storage under
`tests/.runtime`, then Playwright shuts both services down. It does not reuse
the normal preview ports or production data.

The default browser channel is the installed Google Chrome. Set
`E2E_BROWSER_CHANNEL=chromium` after running `npm run test:e2e:install` when a
bundled Chromium is preferred. To test an already running deployment, set
`E2E_BASE_URL` and `E2E_REUSE_SERVER=1`.

## Adding a journey

1. Put reusable selectors and actions in `e2e/pages`.
2. Put generated accounts or static payloads in `e2e/fixtures` or `fixtures`.
3. Add one focused scenario file under `e2e/specs`.
4. Assert user-visible outcomes and API failures, not implementation details.
5. Never commit access tokens, refresh tokens, API keys, resumes or production
   exports as fixtures.
