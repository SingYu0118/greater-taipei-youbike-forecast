# Deployment Runbook

## 1. Target topology

- Cloudflare Worker Cron: scheduled collection every five minutes.
- Cloudflare R2: immutable raw evidence plus the versioned public forecast snapshot.
- Cloudflare Worker with Static Assets: React production build and same-origin Edge API.
- Optional Cloud Run: native Python inference if future requirements demand request-time scoring.
- GitHub Actions: tests and builds on every push.

## 2. Secret policy

Never commit credentials. Local secrets belong in `.env`; production credentials belong in each platform's encrypted secret store. `.env.example` documents names only.

## 3. Cloudflare collector

Cloud collection is optional during local development. On macOS, the versioned LaunchAgent at `infra/launchd/com.singyu.youbike-collector.plist` can keep the local scheduler alive across terminal sessions. Its absolute project path must be updated if the repository moves. Verify it with `make collector-status` and inspect `data/logs/collector.jsonl` for source-level results.

Do not start the official clock during smoke testing. After functional approval, set `COLLECTION_START_AT` in `.env` to an ISO 8601 timestamp with an explicit offset, install or reload the LaunchAgent, and verify that `/api/v1/data/quality` begins at zero with the same official timestamp.

For later cloud deployment, use the following prerequisites and steps.

Prerequisites: Cloudflare account, Wrangler authentication, and an R2 bucket.

```bash
cd infra/cloudflare-collector
cp wrangler.toml.example wrangler.toml
npx wrangler login
npx wrangler r2 bucket create greater-taipei-youbike-raw
npx wrangler secret put COLLECT_TOKEN
npm run typecheck
npm run deploy
```

After deployment:

1. Verify `/health`.
2. Trigger one authenticated manual collection with the bearer token or wait for cron. If `COLLECT_TOKEN` is absent, the manual route is disabled.
3. Confirm three source objects and one manifest in R2.
4. Confirm the next cron trigger creates new timestamped objects.
5. Configure Cloudflare notifications for Worker failures.

For reproducible model training, create a separate R2 S3 API token with Object Read permission restricted to `greater-taipei-youbike-raw`. Put its endpoint, access key ID, secret access key, and bucket name only in local `.env`, then run `make sync-r2`. Do not reuse the Wrangler OAuth token or grant write permission to the training pipeline.

## 4. Backend

```bash
docker build --build-arg GIT_COMMIT="$(git rev-parse HEAD)" -t greater-taipei-youbike-api .
docker run --rm -p 8080:8080 --env-file .env greater-taipei-youbike-api
```

The supplied FastAPI image remains the reference native-Python runtime. The current public demo does not require Cloud Run: the offline publisher loads the validated CatBoost artifact and stores a versioned forecast snapshot in R2. If request-time scoring is needed later, Cloud Run can mount the artifact or download a pinned object at startup; keep all R2 values in its secret store.

## 5. Frontend

For the current same-origin Worker deployment, leave `VITE_API_BASE_URL` empty. For an optional separate backend, set it to that HTTPS API origin before building:

```bash
cd frontend
npm ci
npm run build
```

Deploy `frontend/dist`. Add the public frontend origin to backend `ALLOWED_ORIGINS` before production release.

## 6. Documentation website

Current production URLs:

- [Product application](https://greater-taipei-youbike-app.singyu-bravetalk.workers.dev)
- [English documentation](https://greater-taipei-youbike-docs.singyu-bravetalk.workers.dev)
- [Traditional Chinese documentation](https://greater-taipei-youbike-docs.singyu-bravetalk.workers.dev/zh-Hant/)

The bilingual Docusaurus site lives in `docs-site`. It builds English at `/` and Traditional
Chinese at `/zh-Hant/`, with the shared documentation routes under `/docs`. The production
command is `npm ci && npm run build`, and the static output directory is `docs-site/build`.
Cloudflare Pages or Vercel can deploy it without a server or runtime secret. Configure the
provider's root directory as `docs-site`, build command as `npm run build`, and output directory
as `build`. Set `PRODUCT_APP_URL` to the deployed React application URL when the documentation
site is built. Set `VITE_DOCS_URL` in the React build environment to the deployed documentation
URL. These public configuration values create the bidirectional Product ↔ Documentation links;
they are not credentials.

The public product is deployed as a Cloudflare Worker with Static Assets using
`infra/app-worker/wrangler.toml`. Its same-origin Edge API serves live inventory, formal metrics
and drivers, and the published station-level forecast snapshot. The offline publisher writes
`control/latest-forecasts.json`; the App always displays its forecast origin time.

The same Worker binds the raw R2 bucket as `RAW_BUCKET`. The public quality route reads only
`control/collection-quality.json`; forecast and what-if routes read only
`control/latest-forecasts.json`. Responses are schema-checked and sanitized. Raw history keys,
payloads, cost-guard details, and credentials never enter a public response. Cache headers limit
Class B reads while allowing a new snapshot to appear without rebuilding the frontend.

With Wrangler authenticated locally, reproducible releases are:

```bash
make deploy-product
make deploy-docs
youbike-publish-forecasts
```

## 7. Rollback

- Frontend: redeploy the previous immutable hosting build.
- Backend: route Cloud Run traffic to the previous revision.
- Model: change the model object version referenced by the backend and restart the revision.
- Collector: deploy the previous Worker version. Never delete raw data during rollback.

## 8. Cost guardrails

- Set Cloud Billing budget alerts before enabling Cloud Run.
- Keep Cloud Run minimum instances at zero.
- Store raw data compressed and add an R2 lifecycle rule only after the assignment retention requirement is satisfied.
- Do not poll weather every five minutes; preserve one issue-time forecast per hour.
- The Cloudflare collector requires `COLLECTION_END_AT` and stops before any fetch or R2 write at that instant.
- `MAX_OBJECT_BYTES` rejects unexpectedly large upstream payloads before storage and is capped in code at 1 MB.
- Before each run, `control/cost-guard.json` conservatively reserves six writes and 4 MB, including the collection-quality state update. Collection stops before upstream fetches at 10,000 reserved writes or 8 GB, and emits a warning at 80% of either project limit.
- The public health route performs no R2 operation, so arbitrary health traffic cannot consume billable Class B reads. Detailed guard state remains in the internal control object and Worker logs.
- The public quality route reads one small control object and applies a five-minute shared cache; it never lists or returns raw history.
- With a five-minute Cron, the configured five-day window has fewer than 1,500 invocations and 6,000 Class A writes, far below R2's one-million monthly free allowance.
- Cloudflare budget notifications are alerts, not a guaranteed billing cutoff. The application deadline and payload cap are the enforceable project-level cutoff; remove the Cron after evidence is downloaded.

