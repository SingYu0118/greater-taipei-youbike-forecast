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

Prerequisites: Cloudflare account, Wrangler authentication, and an R2 bucket.

```bash
cd infra/cloudflare-collector
cp wrangler.toml.example wrangler.toml
npx wrangler login
npx wrangler r2 bucket create greater-taipei-youbike-raw
npm run typecheck
npm run deploy
```

After deployment:

1. Verify `/health`.
2. Trigger one authenticated manual collection or wait for cron.
3. Confirm three source objects and one manifest in R2.
4. Confirm the next cron trigger creates new timestamped objects.
5. Configure Cloudflare notifications for Worker failures.

## 4. Backend

```bash
docker build -t greater-taipei-youbike-api .
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

