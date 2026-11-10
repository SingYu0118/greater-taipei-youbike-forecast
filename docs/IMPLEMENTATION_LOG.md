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
- Added out-of-fold uncertainty calibration, final-holdout subgroup metrics, permutation importance, and global/local SHAP reports.
- Added evidence-gated forecast, metrics, drivers, data-quality, and weather what-if API routes.
- Built the React/TypeScript map application and FastAPI service.
- Added responsive desktop/mobile QA, a visible 120-hour collection gate, and live scheduler outcomes.
- Removed known frontend dependency advisories and verified zero reported npm vulnerabilities in both Node projects.
- Passed Python lint and 11 tests, frontend lint and production build, Cloudflare Worker typecheck, and the first GitHub Actions workflow.

### Evidence still pending

- Cloud deployment credentials and public URLs.
- Five complete days of scheduled raw objects.
- First eligible one-hour labels.
- Real-history model results, SHAP drivers, and what-if measurements.
- Public deployment smoke tests.

This log records only observed work. Future entries will include exact commands, test outcomes, deployment revisions, collection coverage, and model metrics.

## 2026-11-10

### Completed

- Added a versioned macOS LaunchAgent and verified that it starts, remains running, writes successful snapshots, and can be stopped cleanly.
- Separated retained development snapshots from the not-yet-started official five-day evidence window.
- Added an explicit `COLLECTION_START_AT` configuration with timezone validation.
- Enforced serving gates for five-day duration, 95% collection completeness, and final-holdout MAE improvement over persistence.
- Changed every temporal and spatial station join to the compound `(source, station_id)` key and added a collision regression test.
- Connected the React application to ready-state forecasts, uncertainty ranges, final metrics, SHAP drivers, and interactive weather what-if scenarios.
- Changed map risk colors and network statistics to use one-hour predictions when the model is ready.
- Built and health-checked the production container as an unprivileged user; verified HTTP 200 health and HTTP 503 before model publication.
- Verified desktop and 390-pixel mobile layouts, live map rendering, station search, city filtering, zero horizontal overflow, and zero browser console errors.
- Passed Python lint and 15 tests, frontend lint and production build, Worker typecheck, and zero-vulnerability npm audits.

### Deliberately deferred

- Official collection start, until the functional review is accepted.
- Cloud resources and public deployment.
- Real-history metrics, which cannot exist before the official collection window is complete.

