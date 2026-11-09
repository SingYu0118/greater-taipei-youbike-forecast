# Implementation Log

## 2026-11-09

### Completed

- Confirmed the live Taipei schema against the official endpoint.
- Confirmed the live New Taipei schema and pagination parameters.
- Implemented independent asynchronous collectors with bounded retry and timeout.
- Implemented local atomic gzip storage and an R2-compatible storage adapter.
- Implemented a Cloudflare Worker scheduled every five minutes.
- Stored the first verified local raw snapshot: 1,824 Taipei stations, 1,622 New Taipei stations, and three weather grids.
- Added a five-minute local scheduler that survives individual collection failures and writes JSONL run logs.
- Versioned 110 official Taipei Metro station coordinates from the Taipei City Data Platform.
- Rebuilt the first two station snapshots into 3,446 normalized Parquet rows.
- Added checksum-based object naming, source/date/hour partitions, and dataset manifests.
- Added source-specific normalization and invariant validation.
- Added 60-minute label alignment logic, lag and rolling feature definitions.
- Added persistence, trend, previous-hour, Ridge, Extra Trees, LightGBM, and CatBoost model competitors.
- Added final 24-hour holdout and three expanding 12-hour validation windows with a 60-minute purge gap.
- Built the initial React/TypeScript map application and FastAPI live endpoint.
- Passed Python lint, Python unit tests, frontend production build, and Cloudflare Worker typecheck.

### Evidence still pending

- Cloud deployment credentials and public URLs.
- Five complete days of scheduled R2 objects.
- First eligible one-hour labels.
- Model results, SHAP drivers, and what-if measurements.
- Final browser and mobile visual QA.

This log records only observed work. Future entries will include exact commands, test outcomes, deployment revisions, collection coverage, and model metrics.

