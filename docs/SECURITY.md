# Security and Operations

## Secret handling

- Local credentials are read only from `.env`, which is excluded from Git.
- `.env.example` contains names and safe defaults only.
- Production secrets must use the hosting platform's encrypted secret store.
- R2 access keys are server-side only and are never included in frontend builds.

## Application boundaries

- Public API routes are read-only except the what-if route, which performs an in-memory prediction and writes no state.
- The optional Worker manual-collection route requires a bearer token stored as a Worker secret; without that secret the route is disabled. Scheduled cron collection does not require a public trigger.
- CORS is configured from `ALLOWED_ORIGINS`; production must use explicit HTTPS origins.
- Upstream API failures return generic client messages rather than leaking internal response bodies.
- Numeric scenario inputs have bounded validation.
- The container runs as an unprivileged user and exposes a health check.

## Supply-chain checks

GitHub Actions installs locked frontend and Worker dependencies, runs Python static checks and tests, compiles TypeScript, and builds the frontend on every push. Local release checks additionally run `npm audit` for both Node projects and build the backend container when Docker is available.

## Before public deployment

1. Restrict `ALLOWED_ORIGINS` to the final frontend domain.
2. Set budget alerts before enabling any billable cloud service.
3. Enable provider logs and failure notifications without logging credentials.
4. Verify the model artifact checksum and training metadata.
5. Run public health, CORS, freshness, API-contract, and mobile smoke tests.
6. Confirm the API still returns HTTP 503 if validated model artifacts are absent.

## Incident rollback

Frontend, backend, collector, and model artifacts are versioned independently. Roll back to the last verified immutable revision; never delete raw history as part of a rollback.
