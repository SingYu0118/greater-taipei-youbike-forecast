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
- Started the official evidence window at 2026-11-10 15:51:49 Asia/Taipei and verified the first local run for 1,824 Taipei and 1,622 New Taipei stations.
- Enabled R2 Standard storage on the free tier, created `greater-taipei-youbike-raw`, and deployed Worker version `5f39a239-6e3a-42d5-ac3b-0df9682fff6b` with a five-minute Cron.
- Added fail-closed Cloudflare cost controls: a fixed stop time, 1 MB object limit, conservative 10,000-write and 8 GB stops, and an 80% warning state.
- Removed R2 reads from the public health route so unsolicited traffic cannot consume Class B operations.
- Deployed Worker version `cfe13c8e-882d-40d5-bf51-ef0902ced73a` with an authoritative private R2 quality state reconstructed from immutable object keys and updated from every later manifest.
- Verified the first cloud quality report at 18.82 observed hours: 215/226 Taipei objects, 215/226 New Taipei objects, 95.13% minimum station completeness, and three complete tracked runs with no post-initialization failure.
- Rebuilt the current local preview dataset (237,774 station rows), created 183,492 feature rows across 3,399 stations, and found 94,936 currently eligible labelled rows across 56 timestamps.
- Confirmed that training fails closed with `Not enough time coverage to create at least two valid expanding folds`; no provisional model was published.
- Restored the missing `youbike-build-features` editable CLI and pinned its Hatchling editable build requirement.
- Created a bucket-scoped Object Read Only credential workflow and completed the first authenticated sync: 795 listed objects, 534 verified source snapshots, and approximately 56 MB downloaded without exposing credentials.
- Separated `data/cloud_raw` formal evidence from `data/raw` laptop backup data, then rebuilt 516 cloud-only station snapshots into 889,068 normalized rows and 876,684 feature rows across 3,399 stations.
- Re-ran the formal trainer on cloud-only features; it correctly remained closed because the current 21-hour range cannot form the required purged expanding folds and final holdout.
- Diagnosed and fixed R2's fixed-length upload requirement, then verified successful 16:50, 16:55, 17:00, and 17:05 Asia/Taipei Cron runs; the 17:00 run also exercised the hourly weather path.

### Remaining evidence

- Complete at least 120 hours of official collection with at least 95% snapshot completeness.
- Build the final reproducible dataset and run model selection on real history.
- Publish final-holdout metrics, drivers, what-if results, production application URLs, and the final presentation.

