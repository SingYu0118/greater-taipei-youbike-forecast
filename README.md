# Greater Taipei YouBike Forecast

[English](README.md) | [繁體中文](README.zh-TW.md)

An end-to-end machine-learning system that forecasts the number of available bikes at every Taipei and New Taipei YouBike station one hour ahead.

> Status: official collection began at 2026-11-10 15:51:49 Asia/Taipei. The local scheduler and a cost-guarded Cloudflare Worker are collecting immutable history. Model results will only be published after the required time-ordered history and untouched final holdout gates pass.

## System goals

- Preserve immutable, timestamped raw API responses.
- Build a documented dataset reproducibly from raw snapshots.
- Compare multiple baselines and model families with leakage-safe rolling validation.
- Explain global and station-level forecast drivers, including weather what-if scenarios.
- Serve a responsive public dashboard and a versioned prediction API.

## Architecture at a glance

The production design separates collection from the user-facing application. A scheduled collector writes immutable source snapshots; deterministic jobs rebuild Parquet datasets and time-safe features; multiple model families compete on expanding future windows; FastAPI serves the selected artifact; and a React application renders the network map, uncertainty, drivers, and scenarios.

The Cloudflare Worker collector is deployed at `https://greater-taipei-youbike-collector.singyu-bravetalk.workers.dev` with a five-minute Cron and Standard-class R2 storage. It has a fixed collection deadline, a 1 MB object cap, conservative 10,000-write and 8 GB project stops, and an 80% warning state. The local LaunchAgent remains active as a temporary independent backup. The application reports `collecting-training-data` until the minimum history, completeness, and untouched final evaluation gates are met. It never substitutes a demo prediction for a trained result.

## Local development

Python 3.12 and Node.js 20+ are recommended.

```bash
cp .env.example .env
make install
make test
make collect
```

Run the services in separate terminals:

```bash
make api
make frontend
```

Then open `http://localhost:5173` and API documentation at `http://localhost:8000/docs`.

Run the bilingual documentation website:

```bash
make docs-install
make docs
```

Open `http://localhost:3000`. The site provides categorized left navigation, local full-text
search, dark/light modes, responsive layouts, and an English/Traditional Chinese switch. A
production build is written to `docs-site/build` by `make docs-build`.

The React product and documentation site link to each other. Local defaults are
`http://localhost:5173` and `http://localhost:3000`; deployment builds use `PRODUCT_APP_URL`
for the documentation site and `VITE_DOCS_URL` for the product frontend.

Run the five-minute local scheduler when cloud collection is not enabled:

```bash
make collect-scheduled
```

The machine must remain awake and online. Run logs are written to `data/logs/collector.jsonl`.

Sync the private R2 evidence before a formal dataset or model run:

```bash
make sync-r2
make dataset
make features
make train
```

R2 credentials remain in `.env`; they are never committed. Preview runs made before the five-day gate are diagnostic only and cannot be published by the serving layer.

## Data contract

The raw layer stores source responses without rewriting them. Object keys are partitioned by source, UTC date, and UTC hour. Every object name includes its fetch timestamp and content checksum. Normalization preserves the original source, update timestamp, station capacity, available bikes, docks, and New Taipei mechanical/e-bike counts.

## Leakage policy

- Samples are split by complete timestamps, never randomly by row.
- Training ends at least 60 minutes before validation starts.
- The final 24 hours are held out before model selection.
- Weather features for `t + 60 minutes` use only forecasts issued at or before `t`.
- Hyperparameter selection uses expanding-window folds only; the final test is evaluated once.

Generated metrics and deployment evidence will be added only after their corresponding gates pass.

## Technical documentation

- [Product design system](design.md)
- [System architecture](docs/ARCHITECTURE.md)
- [Data pipeline](docs/DATA_PIPELINE.md)
- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Modeling and time validation](docs/MODELING.md)
- [Model candidate review](docs/MODEL_CANDIDATE_REVIEW.md)
- [API contract](docs/API.md)
- [Testing strategy](docs/TESTING.md)
- [Deployment runbook](docs/DEPLOYMENT.md)
- [Implementation log](docs/IMPLEMENTATION_LOG.md)
- [Data sources and provenance](docs/SOURCES.md)
- [Security and operations](docs/SECURITY.md)
- [Presentation content outline](docs/PRESENTATION_OUTLINE.md)

## Verified quality gates

```bash
ruff check src tests
pytest
cd frontend && npm run lint && npm run build && npm audit
cd infra/cloudflare-collector && npm run typecheck && npm audit
cd docs-site && npm run typecheck && npm run build && npm audit
```

The test suite includes a complete synthetic seven-model competition across Ridge, Random Forest, Extra Trees, Histogram Gradient Boosting, LightGBM, XGBoost, and CatBoost, with three purged expanding-window folds and a final 24-hour holdout. Real-data metrics will only be published after the required history exists.
