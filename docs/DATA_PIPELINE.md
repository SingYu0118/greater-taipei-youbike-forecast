# Data Pipeline

## 1. Source inventory

### Taipei YouBike

- Format: one JSON array containing the current state of all stations.
- Observed fields: station ID, Chinese and English names, district, address, coordinates, capacity, rentable bikes, returnable docks, activity flag, and multiple source timestamps.
- Collection: one request every five minutes.

### New Taipei YouBike

- Format: paginated JSON arrays using `page` and `size`.
- Important difference: most numeric values are strings. Mechanical and electric bike counts are supplied separately.
- Collection: request pages until a page contains fewer rows than the configured page size. IDs are checked for duplicates across pages.

### Open-Meteo

- Three representative grid points cover central Taipei, western Greater Taipei, and eastern Greater Taipei.
- Each hourly snapshot stores the full 48-hour forecast and its issue time.
- Variables include temperature, apparent temperature, relative humidity, precipitation, precipitation probability, weather code, wind speed, and gusts.

## 2. Raw object contract

```text
source=<source>/date=<UTC date>/hour=<UTC hour>/
  <UTC fetch timestamp>-<first 12 SHA-256 characters>.json.gz
```

The unmodified API response is encoded as UTF-8 JSON before hashing and gzip compression. Cloud objects contain `sha256` and `fetched_at` metadata. Raw objects are never edited by a downstream job.

## 3. Normalization

Every raw station object produces one Parquet shard. This one-to-one mapping makes incremental rebuilds idempotent and gives a direct audit path from a processed row to a raw response.

Source timestamps are parsed as Asia/Taipei and stored as UTC. Fetch time and source update time are separate fields. The pipeline does not substitute one for the other.

Validation rejects:

- empty snapshots;
- duplicate station IDs within a snapshot;
- negative capacity, bike, or dock counts;
- rentable-bike counts greater than capacity;
- unsupported timestamp formats.

## 4. Label alignment

For an observation at time `t`, the target is the same station's rentable-bike count nearest `t + 60 minutes`. The accepted tolerance is plus or minus seven minutes. Samples outside that tolerance are excluded instead of being assigned a misleading label.

Target fields are used only as labels and evaluation outcomes. They never become predictor features.

## 5. Feature availability policy

A feature is eligible only if it was available at or before the prediction timestamp.

- Bike lags use snapshots no later than `t - lag`.
- Rolling statistics end at `t`.
- Calendar values are deterministic and known in advance.
- A future weather value must come from a forecast issued at or before `t`.
- Event data is excluded from version one because historical publication timestamps are difficult to establish reliably.

## 6. Reproducibility

```bash
youbike-build-dataset
youbike-build-features
youbike-train
```

Each stage fails loudly when its required inputs are missing. Dataset and model manifests record creation time, code version, row counts, time coverage, station coverage, model name, and validation results.

## 7. Data-quality reporting

The final report will include:

- expected versus successful collection runs;
- maximum and median gap between snapshots;
- source update delay relative to fetch time;
- station count changes;
- duplicate and invalid row counts;
- target-match coverage;
- weather-forecast match coverage;
- missing-feature rates by column.

