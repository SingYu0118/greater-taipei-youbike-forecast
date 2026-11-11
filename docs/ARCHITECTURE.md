# System Architecture

## 1. Purpose

The system predicts the number of rentable bikes at each Taipei and New Taipei YouBike station 60 minutes ahead. It is designed as a complete data product rather than a notebook: collection, immutable history, reproducible processing, leakage-safe model selection, an inference API, a responsive web application, monitoring, and technical documentation are versioned together.

## 2. Architecture decisions

| Concern | Decision | Rationale |
|---|---|---|
| Collection cadence | Every five minutes | Captures short commuter flows while keeping API and storage load modest. |
| Raw history | Immutable gzip JSON in Cloudflare R2 | Preserves evidence, supports replay, and fits the free tier. |
| Local analytics | Partitioned Parquet with DuckDB and Polars | Efficient for millions of snapshot rows without operating a database server. |
| Model service | Python FastAPI on Google Cloud Run | Native Python model loading, scale-to-zero, documented OpenAPI contract. |
| Web application | React, TypeScript, MapLibre | More product-quality interaction and visual control than a notebook-style UI. |
| Web hosting | Vercel or Cloudflare Pages | Static assets are globally cached and independently deployable. |
| Scheduled collector | Cloudflare Worker Cron | The five-day collection does not depend on a laptop remaining online. |

The official collection window began on 2026-11-10. A Cloudflare Worker Cron writes to Standard-class R2 every five minutes, while the versioned macOS LaunchAgent remains active as a temporary independent backup. The Worker stops automatically after the evidence window and enforces conservative write, storage, and per-object limits before upstream collection.

R2 is also the authority for formal completeness. Immutable source objects and per-run manifests remain the audit evidence, while `control/collection-quality.json` is a reconstructable incremental index used for live gate status. The laptop log is diagnostic backup evidence and cannot lower cloud completeness when the machine sleeps.

## 3. Runtime flow

```text
Taipei live API ----------+
New Taipei paged API -----+--> Cloudflare Worker (every 5 min)
Open-Meteo forecast ------+       | retries, timeouts, validation
                                  v
                         Cloudflare R2 raw history
                         source/date/hour/object.json.gz
                                  |
                                  v
                 deterministic normalization pipeline
                       partitioned Parquet shards
                                  |
                                  v
                   leakage-safe feature generation
             lags + rolling flow + calendar + weather + space
                                  |
                   expanding-window model competition
                  /               |                 \
             baselines       linear model       tree ensembles
                  \               |                 /
                    untouched final 24-hour test
                                  |
                          versioned model bundle
                                  |
                      FastAPI <----> React dashboard
```

## 4. Failure boundaries

The Taipei, New Taipei, and weather requests are independent jobs. A failure in one source does not erase successful responses from another source. Each scheduled run writes a manifest containing every outcome. Failed requests use bounded exponential backoff. New Taipei pagination has a safety limit and duplicate-station validation. Objects are named with the fetch timestamp and a content checksum, so retries cannot silently overwrite unrelated history.

The local Python collector uses temporary files, `fsync`, and atomic rename. The cloud collector streams gzip content directly to R2 and attaches the SHA-256 checksum as object metadata.

## 5. Security boundaries

- Secrets are accepted only through environment variables or deployment-platform secret stores.
- `.env` and generated datasets are excluded from Git.
- The browser never receives R2 credentials.
- CORS origins are explicit in production.
- Public endpoints are read-only except in-memory what-if inference. The optional manual collection route requires a Worker-secret bearer token and is disabled when the secret is absent.

## 6. Current implementation status

Implemented and locally verified:

- Taipei and fully paginated New Taipei collection.
- Open-Meteo issue-time forecast collection for three Greater Taipei grid points.
- Local atomic gzip storage and Cloudflare R2 Worker implementation.
- Source-specific normalization to one documented station schema.
- Incremental raw-to-Parquet reconstruction.
- Expanding-window split utility with a 60-minute purge gap and final holdout.
- Seven-model competition, out-of-fold prediction interval calibration, subgroup evaluation, and SHAP/permutation driver reports.
- React map application and evidence-gated FastAPI forecast, metrics, drivers, quality, and what-if endpoints.
- Python tests, static checks, frontend production build, and Worker typecheck.

Pending evidence gates:

- Five complete days of official history.
- Real-history final model comparison metrics.
- Real-history SHAP results and weather what-if measurements.
- Production URLs and cloud health checks.

