# Deployment Runbook

## 1. Target topology

- Cloudflare Worker Cron: scheduled collection every five minutes.
- Cloudflare R2: immutable compressed raw objects and run manifests.
- Google Cloud Run: containerized FastAPI and Python model runtime.
- Vercel or Cloudflare Pages: React production build.
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

## 4. Backend

```bash
docker build --build-arg GIT_COMMIT="$(git rev-parse HEAD)" -t greater-taipei-youbike-api .
docker run --rm -p 8080:8080 --env-file .env greater-taipei-youbike-api
```

For Cloud Run, store R2 access values as secrets and mount the trained model artifact during the deployment build or download a versioned object during startup. Set minimum instances to zero to remain within the free tier; expect a cold start during an inactive demo.

## 5. Frontend

Set `VITE_API_BASE_URL` to the Cloud Run HTTPS URL and build:

```bash
cd frontend
npm ci
npm run build
```

Deploy `frontend/dist`. Add the public frontend origin to backend `ALLOWED_ORIGINS` before production release.

## 6. Rollback

- Frontend: redeploy the previous immutable hosting build.
- Backend: route Cloud Run traffic to the previous revision.
- Model: change the model object version referenced by the backend and restart the revision.
- Collector: deploy the previous Worker version. Never delete raw data during rollback.

## 7. Cost guardrails

- Set Cloud Billing budget alerts before enabling Cloud Run.
- Keep Cloud Run minimum instances at zero.
- Store raw data compressed and add an R2 lifecycle rule only after the assignment retention requirement is satisfied.
- Do not poll weather every five minutes; preserve one issue-time forecast per hour.
- The Cloudflare collector requires `COLLECTION_END_AT` and stops before any fetch or R2 write at that instant.
- `MAX_OBJECT_BYTES` rejects unexpectedly large upstream payloads before storage and is capped in code at 1 MB.
- Before each run, `control/cost-guard.json` conservatively reserves five writes and 4 MB. Collection stops before upstream fetches at 10,000 reserved writes or 8 GB, and emits a warning at 80% of either project limit.
- The public health route performs no R2 operation, so arbitrary health traffic cannot consume billable Class B reads. Detailed guard state remains in the internal control object and Worker logs.
- With a five-minute Cron, the configured five-day window has fewer than 1,500 invocations and 6,000 Class A writes, far below R2's one-million monthly free allowance.
- Cloudflare budget notifications are alerts, not a guaranteed billing cutoff. The application deadline and payload cap are the enforceable project-level cutoff; remove the Cron after evidence is downloaded.

