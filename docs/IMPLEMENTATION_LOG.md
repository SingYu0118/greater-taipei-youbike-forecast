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
- Added persistence, trend, and previous-hour baselines plus Ridge, Random Forest, Extra Trees, Histogram Gradient Boosting, LightGBM, XGBoost, and CatBoost model competitors.
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

## 2026-11-11

### Completed

- Reviewed model families against the actual five-day, multi-station, direct 60-minute forecasting design and documented explicit inclusion and deferral criteria.
- Expanded the formal competition from four to seven learned candidates by adding Random Forest, Histogram Gradient Boosting, and XGBoost.
- Retained one shared leakage-safe evaluation protocol for every candidate rather than giving any model a favourable split.
- Added XGBoost to the reproducible model dependency group and verified installation in the project environment.
- Selected the CPU-only XGBoost package for Linux containers after a Docker build exposed the standard package's unnecessary NVIDIA NCCL dependency.
- Rebuilt the production image successfully and verified inside the Linux container that XGBoost 3.4.1 imports and all seven candidate factories are available.
- Passed Python lint and all 20 tests, including the complete synthetic seven-model competition, artifact serialization, API inference, prediction intervals, and weather what-if flow.
- Re-ran the formal trainer and confirmed that it still fails closed before fitting candidates because the official history has not yet reached the required time coverage.
- Deployed the React product and same-origin live-station Edge API to `https://greater-taipei-youbike-app.singyu-bravetalk.workers.dev`.
- Deployed the bilingual Docusaurus site to `https://greater-taipei-youbike-docs.singyu-bravetalk.workers.dev`.
- Verified HTTP 200 for the product, English documentation, and Traditional Chinese documentation; the public Edge API returned 3,446 normalized live stations during the observed smoke test.
- Kept the model fail-closed in `collecting-training-data`; deployment does not publish preview metrics or forecasts.

### Deferred by evidence, not omitted

- ARIMA/ARIMAX require a separate station-level rolling design and more repeated seasonal history.
- Global neural sequence and graph models require at least one month of history to justify their additional variance and operational cost.

## 2026-11-12

### Completed

- Added the pre-declared 72-hour diagnostic: first 48 hours for training, a 60-minute purge, and the third day as one untouched test shared by all models and baselines.
- Added `make early-diagnostic` to sync R2, rebuild the formal dataset and features, and write a preliminary evaluation without publishing a serving artifact.
- Replaced the product's deployment-time quality snapshot with a live sanitized read of `control/collection-quality.json` from R2.
- Verified automatic progress without redeployment: the public API advanced from 53.99 to 54.07 observed hours and from 425 to 426 complete runs after the next collector cycle.
- Kept the public health route independent of R2 and added five-minute shared caching to the quality route.
- Drafted four English model-selection slides; model-score fields remain intentionally absent until the evidence gates pass.
- Verified that the official Taipei and New Taipei station feeds expose current snapshots rather than a downloadable five-minute inventory archive; official OD and daily availability-rate datasets answer different questions.
- Added a physically isolated practice importer for the MIT-licensed `tses89214/youbike-historical-data` Taipei archive. The default command downloads only four daily CSV files and never writes to formal R2, raw, processed, feature, or model paths.
- Completed a real development-only 72-hour diagnostic on 120 sampled Taipei stations: 30,257 feature rows, 15,634 training rows, and 2,211 untouched day-three rows. CatBoost was the best learned candidate at MAE 4.210, but persistence remained better at MAE 4.142, so the improvement was -1.63% and no publication gate passed.
- Recorded the practice limitations explicitly: Taipei only, publisher `infoTime` used as the observation timestamp, and constant weather placeholders with no predictive signal. These results validate plumbing and time splits but are not formal assignment evidence.

## 2026-11-13

### Completed

- Crossed the early-diagnostic raw-history threshold at 74.07 observed station hours with 98.43% station completeness, 663 complete tracked runs, three partial failures, and no complete failures.
- Synced 2,678 R2 objects, verified 1,267 source objects, rebuilt 1,732 station snapshots and 73 issue-time weather snapshots, and generated 2,980,672 feature rows across 3,401 stations.
- Ran the pre-declared official-window diagnostic with 1,919,352 training rows, a 60-minute purge, and 971,474 untouched third-day test rows.
- XGBoost ranked first on third-day MAE at 2.547 versus persistence at 2.777, an 8.30% preliminary improvement. CatBoost, LightGBM, and Histogram Gradient Boosting followed closely at 2.559, 2.567, and 2.569 MAE.
- Kept the publication gate closed because the diagnostic has only one test day and does not replace the five-day rolling validation and final holdout.
- Identified operational-risk recall as the main weakness: XGBoost empty/full recall was 34.82%/6.96%, below persistence at 65.26%/43.39%. The formal report will retain both regression and risk metrics.

## 2026-11-15

### Completed

- Closed the formal collection window above 120 observed hours with 99.04% minimum station completeness, 1,228 complete tracked runs, four partial failures, and no complete failures.
- Rebuilt 4,897,388 feature rows across 3,402 observed stations; 4,858,440 eligible labelled rows across 3,401 stations entered formal evaluation.
- Completed the seven-model competition with three purged expanding folds and a separate 976,209-row final holdout.
- Selected CatBoost by mean CV MAE: 2.609 versus 2.611 for XGBoost.
- CatBoost achieved final MAE 2.026 and RMSE 3.500, versus persistence at 2.056 and 3.701. The regression publication gate passed.
- Preserved the operational limitation: CatBoost empty/full recall was 35.24%/20.66%, below persistence at 62.76%/53.84%.
- Generated the versioned model bundle, evaluation report, permutation importance, global SHAP, and a local SHAP example.
- Published formal metrics and drivers in the public edge product without representing live station inventory as model output.

