# Engineering Implementation Record

This page records the implemented system, technical contracts, verification boundaries, and
operational controls. Model scores are maintained separately in
[Final Five-Day Model Results](./FINAL_RESULTS.md).

## Runtime architecture

| Component | Implementation | Responsibility |
|---|---|---|
| Scheduled collector | Cloudflare Worker Cron | Fetch Taipei, paged New Taipei, and issue-time Open-Meteo data |
| Evidence store | Cloudflare R2 Standard | Retain immutable compressed responses, manifests, and control objects |
| Reproducible pipeline | Python, Polars, DuckDB, Parquet | Normalize raw objects, validate invariants, align labels, and build features |
| Model pipeline | scikit-learn, LightGBM, XGBoost, CatBoost | Run baselines, temporal validation, final evaluation, and explanation |
| Inference service | FastAPI `ForecastService` | Load the validated artifact and produce bounded station forecasts |
| Public serving layer | Cloudflare Worker + R2 snapshot | Serve forecast, quality, metrics, drivers, and what-if contracts |
| Product | React, TypeScript, MapLibre | Search, city navigation, risk map, station detail, and evidence |
| Documentation | Docusaurus | Publish English and Traditional Chinese technical contracts |

## Collection and failure handling

The collector runs on a five-minute Cron. Taipei and New Taipei are fetched independently, so one
upstream failure does not discard a successful source. Requests use bounded timeout and retry; New
Taipei pagination also has a safety limit.

Every run writes a source-level manifest. A run can be complete, partial, or failed without hiding
the failed upstream. The quality controller reconstructs its state from immutable objects instead
of trusting process-local counters.

Raw station object contract:

```text
source={source}/date=YYYY-MM-DD/hour=HH/
YYYYMMDDTHHMMSS.ffffffZ-{sha256-prefix}.json.gz
```

The uncompressed JSON SHA-256 is stored in metadata and repeated in the filename. R2 sync validates
gzip integrity, metadata checksum, filename checksum, and byte count before formal processing.

## Cost and security controls

- The official collection has a fixed stop condition and fails closed on object-size, write-count,
  or storage-volume limits.
- An 80% warning state is written before a hard cost guard is reached.
- The public health route does not read R2.
- R2 access is bucket-bound; the local S3 credential remains read-only.
- Credentials come only from `.env` or platform secrets and are excluded from Git.
- Public Worker responses are cached and remain subject to Free-plan limits.

## Normalized data contract

Taipei and New Taipei are mapped into one station schema containing compound identity
`(source, station_id)`, station metadata, coordinates, capacity, bikes, docks, upstream update time,
and collector fetch time.

Every temporal and spatial join uses the compound identity. Numeric station IDs can collide across
municipalities, so `station_id` alone is never a valid join key. Normalization rejects malformed
coordinates, negative inventory, and inconsistent capacity.

Parquet artifacts are reproducible from R2 raw history. Development data, practice history, laptop
backup snapshots, and the formal evidence window use physically separate directories.

## Target and feature contract

For each station row at time `t`, the target is the same compound station at `t + 60 minutes`.
Only the closest observation within ±7 minutes is accepted. Rows without a valid future target stay
available for inference but are excluded from supervised evaluation.

The 35 model inputs cover:

- current inventory, docks, capacity, and bike ratio;
- 5, 15, 30, and 60-minute lags, deltas, rolling mean, and variation;
- hour, weekday, weekend, cyclic hour encoding, and Taiwan holidays;
- nearest MRT distance and station/district/source codes;
- up to five neighbours within one kilometre and their current bike statistics;
- issue-time temperature, apparent temperature, humidity, precipitation, probability, weather
  code, wind speed, and gusts.

Weather joins use forecasts archived at issue time. Future station state and realized future weather
never enter a prediction-time row.

## Temporal evaluation contract

The final 24 hours are removed before selection as an untouched holdout. The remaining development
window creates three expanding folds, each with a 12-hour validation window and a 60-minute purge.

Persistence, recent trend, and previous-hour baselines use the same timestamps as Ridge, Random
Forest, Extra Trees, Histogram Gradient Boosting, LightGBM, XGBoost, and CatBoost. Selection uses
mean validation MAE, then RMSE. The final holdout is evaluated once after selection.

Publication fails closed unless:

1. the verified collection window is at least 120 hours;
2. minimum station completeness is at least 95%;
3. the selected model beats persistence on final-holdout MAE.

## Model artifact contract

| Artifact | Content |
|---|---|
| `model.joblib` | fitted pipeline, feature order, category maps, q90 residual band, metadata |
| `evaluation.json` | fold ranking, final and segment metrics, timings, publication decision |
| `drivers.json` | global/local SHAP, permutation importance, interpretation cautions |

`ForecastService` refuses inference when required evidence is missing. Predictions are clipped to
`[0, capacity]` and include an empirical q90 error band.

## Public forecast snapshot

The Python publisher loads the validated artifact, scores each freshest station row, and scores dry
and heavy-rain controlled scenarios. It publishes:

```text
control/latest-forecasts.json
```

The object contains schema version, generation time, forecast origin, model metadata, station
count, point predictions, bounded intervals, and scenario predictions. Stations more than 15
minutes older than the maximum observation time are excluded.

| Public route | Contract |
|---|---|
| `GET /health` | serving state without an R2 quality read |
| `GET /api/v1/forecasts/latest` | published station forecast snapshot |
| `POST /api/v1/stations/{id}/what-if` | precomputed controlled weather response |
| `GET /api/v1/model/metrics` | sanitized formal evaluation |
| `GET /api/v1/model/drivers` | sanitized explanation report |
| `GET /api/v1/data/quality` | sanitized collection-quality state |
| `GET /api/v1/stations/live` | normalized official live-inventory fallback |

The UI always displays the forecast origin. A stored prediction is never presented as newer data.

## Product navigation

The React client embeds the versioned official MRT coordinate reference used by feature
engineering. Users can filter the network by one of five Taipei Metro lines, then select a station
in `Chinese name (English name)` format. A line selection fits the complete route and keeps
YouBike stations within 700 metres; a station selection moves to that coordinate and lists the six
nearest YouBike stations within one kilometre with bikes now and the +60-minute prediction.
Chinese and English MRT names are both accepted by the main search field. The forecast publisher
also enriches each station with the official YouBike `snaen` and `sareaen` values. Search and the
station panel therefore support both languages without machine translated names.

## Verification gates

The repository verifies source normalization, upstream failure mapping, compound identity,
cross-city collisions, temporal order, purge gaps, label tolerance, issue-time weather joins,
seven-model artifacts, inference, intervals, what-if behaviour, and ready/not-ready API contracts.

Release checks include Python Ruff and Pytest, React ESLint/TypeScript/build, bilingual Docusaurus
typecheck/build, Worker bundling and HTTP smoke tests, plus desktop and 375-pixel mobile QA for the
map, bilingual MRT search, line/station navigation, station panel, console, and overflow.

## Known engineering limits

- Five days do not contain repeated weekly or seasonal regimes.
- Bike-count error is optimized; empty/full recall needs a separate objective.
- Public prediction uses a versioned R2 batch snapshot, not CatBoost inside a free Worker isolate.
- Event data is deferred until a reliable geocoded event history exists.
- Automatic refresh still needs a bounded scheduled Python publisher; the serving contract is
  independent of scheduler choice.

## Next production increment

1. Run the publisher hourly and reject snapshots outside a declared freshness SLO.
2. Add a dedicated empty/full classifier and tune thresholds on development folds.
3. Add previous-day and previous-week baselines after repeated cycles exist.
4. Monitor snapshot age, feature drift, prediction drift, and segment error.
5. Compare one global sequence or graph model under the same untouched holdout after one month.
