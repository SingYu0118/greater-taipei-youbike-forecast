# Greater Taipei YouBike Forecast

An end-to-end machine-learning system that forecasts the number of available bikes at every Taipei and New Taipei YouBike station one hour ahead.

> Status: the production-grade collector and application are under active construction. Model results will only be published after the required time-ordered history has been collected and the untouched final holdout has been evaluated.

## System goals

- Preserve immutable, timestamped raw API responses.
- Build a documented dataset reproducibly from raw snapshots.
- Compare multiple baselines and model families with leakage-safe rolling validation.
- Explain global and station-level forecast drivers, including weather what-if scenarios.
- Serve a responsive public dashboard and a versioned prediction API.

## Architecture at a glance

The production design separates collection from the user-facing application. A scheduled collector writes immutable source snapshots; deterministic jobs rebuild Parquet datasets and time-safe features; multiple model families compete on expanding future windows; FastAPI serves the selected artifact; and a React application renders the network map, uncertainty, drivers, and scenarios.

The current local collector is running while cloud deployment is intentionally deferred. The application reports `collecting-training-data` until the minimum history and untouched final evaluation gates are met. It never substitutes a demo prediction for a trained result.

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

Run the five-minute local scheduler when cloud collection is not enabled:

```bash
make collect-scheduled
```

The machine must remain awake and online. Run logs are written to `data/logs/collector.jsonl`.

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

- [System architecture](docs/ARCHITECTURE.md)
- [Data pipeline](docs/DATA_PIPELINE.md)
- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Modeling and time validation](docs/MODELING.md)
- [API contract](docs/API.md)
- [Testing strategy](docs/TESTING.md)
- [Deployment runbook](docs/DEPLOYMENT.md)
- [Implementation log](docs/IMPLEMENTATION_LOG.md)
- [Presentation content outline](docs/PRESENTATION_OUTLINE.md)

## Verified quality gates

```bash
ruff check src tests
pytest
cd frontend && npm run lint && npm run build && npm audit
cd infra/cloudflare-collector && npm run typecheck && npm audit
```

The test suite includes a complete synthetic model competition across Ridge, Extra Trees, LightGBM, and CatBoost, with three purged expanding-window folds and a final 24-hour holdout. Real-data metrics will only be published after the required history exists.
