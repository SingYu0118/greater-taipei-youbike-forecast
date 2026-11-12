# Complete Project Guide

This chapter explains the Greater Taipei YouBike forecasting system from the problem statement to production serving. It is written as a thesis-style system report, but each technical choice is followed by a plain-language interpretation.

## Abstract

The system predicts the number of rentable bikes at every active Taipei and New Taipei YouBike station 60 minutes ahead. The main difficulty is not merely choosing a regression algorithm. The official APIs publish current station state but no complete, downloadable five-minute Greater Taipei inventory archive. The project therefore builds the evidence before training: a scheduled collector preserves immutable raw responses, a deterministic pipeline reconstructs a documented dataset, seven model families compete under forward-only validation, and the application publishes forecasts only after an untouched future test beats a strong persistence baseline.

The current production collector is healthy, but the formal 120-hour evidence window is still incomplete. Engineering, synthetic tests, public-history practice, deployment, and validation logic are complete; real-history final model metrics, drivers, and what-if measurements remain pending by design.

## 1. Research question

For station \(s\) observed at time \(t\), estimate:

```text
predicted_bikes(station, t + 60 minutes) = model(information available at t)
```

The target is the number of rentable bikes about 60 minutes later, while the input contains only information available at or before the forecast time. Predictions are clipped to the physical interval from zero to station capacity.

This is an inventory problem, not merely a trip-demand problem. A station can fail in two ways: no bikes are available for departure, or no docks are available for return. The model must therefore preserve station identity and physical capacity.

## 2. Pre-declared success criteria

The following rules were fixed before formal model selection:

1. Collect at least 120 verified hours after the declared official start.
2. Maintain at least 95% station-snapshot completeness.
3. Use forward time splits with a 60-minute purge gap.
4. Keep the final 24 hours untouched during model selection.
5. Select by mean validation MAE, using RMSE as the tie-breaker.
6. Publish only if final-holdout MAE beats persistence, which predicts that the future count equals the current count.
7. Report empty/full risk recall and subgroup errors so a good average cannot hide operational failures.

These constraints turn “the model scored well” into an auditable statement about genuinely later time.

## 3. End-to-end architecture

```text
Taipei live API -----------+
New Taipei paged API ------+--> Cloudflare Worker Cron
Open-Meteo forecast -------+       retries + validation + cost guard
                                    |
                                    v
                         immutable gzip JSON in R2
                                    |
                                    v
                       normalization into Parquet
                                    |
                                    v
                leakage-safe labels and 35 model features
                                    |
                                    v
                baselines + seven learned model families
                                    |
                   three rolling folds + final holdout
                                    |
                                    v
                       versioned model and report
                                    |
                            FastAPI service
                                    |
                         React + MapLibre product
```

The collector, analytical pipeline, model service, product, and documentation are separate layers. A failure can therefore be located without silently corrupting another layer.

## 4. Collection and evidence

Taipei and New Taipei inventory are collected every five minutes. New Taipei pages are fetched until a short final page appears, with a safety limit and duplicate-ID checks. Three Open-Meteo grids are collected hourly, preserving the forecast issue time and a 48-hour horizon.

Each response is stored under a source/date/hour key containing its fetch timestamp and checksum. Objects are immutable. A manifest records success or failure for each source independently, so one upstream failure cannot erase other successful responses.

Cloudflare R2 is the authority for formal completeness. A sanitized control object reports the observed window, expected versus received snapshots, and collection gates. Laptop snapshots remain diagnostic backup and do not inflate cloud completeness.

Cost controls stop collection before exceeding conservative project limits: a fixed end time, a one-megabyte object limit, 10,000 reserved writes, eight gigabytes of reserved storage, and an 80% warning state. These are technical stop controls, not a billing guarantee from the provider.

## 5. Reproducible dataset construction

Raw responses are never edited. Normalization produces a common schema containing source, station ID, name, district, coordinates, capacity, available bikes, available docks, activity state, source update time, and collector fetch time. Taipei and New Taipei IDs are always joined using the compound key `(source, station_id)`.

The formal paths are physically separated from development and community history:

- `data/cloud_raw`: R2 evidence eligible for formal reporting;
- `data/formal_processed`: normalized formal Parquet shards;
- `data/formal_features`: formal labels and features;
- `data/practice_*`: isolated third-party practice data;
- `artifacts/practice`: development-only reports.

This separation prevents an older public snapshot from accidentally satisfying the five-day assignment gate.

## 6. Target construction

For every observation at time \(t\), the pipeline finds the same station nearest \(t+60\) minutes. A match is accepted only within plus or minus seven minutes. If no valid future observation exists, the row is excluded instead of receiving an approximate or incorrect label.

The purge gap is necessary because the label for a row near the end of training points one hour into the future. Without a gap, a training label could overlap the validation period even when feature timestamps appear separate.

## 7. Feature design

The model currently uses 35 structured inputs:

- current inventory: bikes, docks, capacity, and bike ratio;
- recent movement: 5, 15, 30, and 60-minute lags and deltas;
- rolling behaviour: 60-minute mean and standard deviation;
- calendar: hour, cyclic hour encoding, weekday, weekend, and Taiwan holiday;
- issue-time weather: temperature, apparent temperature, humidity, rain, rain probability, weather code, wind, and gusts;
- location: nearest MRT distance;
- neighbouring stations: count and mean inventory within one kilometre, using up to five neighbours;
- identifiers: station, district, and city-source codes.

The critical rule is information availability. Realized future weather is forbidden. A weather value for the target hour is eligible only when it came from a forecast issued no later than the prediction timestamp.

## 8. Why time validation matters

Random splitting is invalid because rows five minutes apart are nearly duplicates. It would allow the model to train on observations surrounding a validation row and produce an unrealistically optimistic score.

Formal evaluation has two levels:

1. Development: three expanding training windows, each followed by a 60-minute purge and a 12-hour validation window.
2. Final test: the last 24 hours are untouched until the model family is selected.

At 72 verified hours, an optional preliminary diagnostic trains on the first 48 hours, applies the same purge, and evaluates the third day. It verifies that the real-data pipeline can learn a signal, but it cannot publish a serving model or replace the five-day evaluation.

## 9. Model competition

Three baselines define the minimum standard: persistence, recent linear trend, and the previous-hour value. Seven learned candidates test different assumptions under identical features and splits:

- Ridge: interpretable linear control;
- Random Forest and Extra Trees: bagged nonlinear trees;
- Histogram Gradient Boosting, LightGBM, XGBoost, and CatBoost: four boosting designs.

A global model is used because five days provide little history per station but millions of rows across the network. The model can share rush-hour and weather patterns while station, district, and source codes retain local differences.

ARIMA/SARIMAX would require thousands of repeatedly fitted station models. LSTM, TFT, N-HiTS, and graph networks require more repeated weekly, weather, and event regimes. They are valid one-month challengers, not automatically superior five-day candidates.

## 10. Metrics and interpretation

- MAE: average number of bikes missed; the primary selection metric.
- RMSE: gives more weight to large errors.
- WAPE: aggregate absolute error relative to observed inventory.
- Empty recall: fraction of actual `<=2 bikes` events correctly warned.
- Full recall: fraction of actual `<=2 docks` events correctly warned.

Errors are also segmented by city, district, hour, weekday/weekend, rain, capacity, and risk class. The winning model stores a 90th-percentile absolute-error interval calibrated from out-of-fold validation errors, never from the final holdout.

## 11. Drivers and what-if analysis

Permutation importance measures how much holdout performance deteriorates when one feature is disrupted. SHAP explains global feature use and an individual station prediction. A rain what-if changes only weather forecast inputs while holding station state and time constant.

These outputs explain model response, not causality. If rain changes a prediction, the correct statement is “the model responds this way under the changed input,” not “rain causes exactly this many bikes to disappear.”

## 12. Product behaviour

The React application always shows the live network, search, city switching, current empty/full risk, and collection progress. When all evidence gates pass, the same interface can show one-hour forecasts, uncertainty, model metrics, drivers, and station-level rain scenarios.

FastAPI validates both the model bundle and its evaluation report. Before the gates pass, forecast routes return HTTP 503 and the product shows `collecting-training-data`. The application never substitutes demo predictions for missing evidence.

## 13. Current evidence status

Snapshot observed at 2026-11-13 00:25 Asia/Taipei:

- official start: 2026-11-10 15:51:49 Asia/Taipei;
- observed history: 56.57 / 120 hours;
- station completeness: 98.38%;
- complete scheduled runs: 456;
- partial failures: 0;
- failures: 0.

The system engineering is complete, but the formal model result is not yet known. The five-day point is approximately 2026-11-15 15:51:49 Asia/Taipei, assuming uninterrupted collection. This status is a dated snapshot; the product quality API is the live authority.

## 14. What has and has not been proven

Proven now:

- both city feeds can be collected, normalized, rebuilt, and served;
- R2 collection continues independently of the laptop;
- the seven-model pipeline, time splits, API gates, Docker image, frontend, documentation, and CI work;
- public-history practice reaches a real model competition without contaminating formal paths.

Not yet proven:

- which learned model wins on the official five-day history;
- whether that model beats persistence on the untouched final day;
- the final real-history SHAP drivers and rain what-if magnitude;
- seasonal, event, or long-holiday robustness.

The isolated practice run selected CatBoost among learned models at MAE 4.210, while persistence achieved MAE 4.142. The learned model was 1.63% worse, so no publication gate passed. That result validates the machinery and shows why a strong baseline matters; it is not the formal assignment result.

## 15. What to do next

Before 72 hours, avoid changing collection cadence, schemas, gates, or model rules unless a real failure occurs. Monitor completeness and failures only.

At 72 hours:

```bash
make early-diagnostic
```

Label the output preliminary. Do not deploy it as the production model.

At 120 hours:

```bash
make sync-r2
make dataset
make features
make train
make test
```

Then review data-quality gaps, fold stability, final-holdout improvement, risk recall, subgroup errors, drivers, and what-if results. Publish only if every gate passes. If persistence still wins, report that honestly and continue collection rather than weakening the test.

## 16. Recommended optimization roadmap

### Now

- Keep the collector unchanged while it is healthy.
- Add no new model solely to make the list longer.
- Prepare result-table and chart templates without inserting invented values.
- Rehearse the problem, leakage rule, baseline gate, and evidence boundary.

### After five days

- Diagnose the winner and weakest subgroups.
- Tune only within rolling development folds if a justified small search is needed.
- Calibrate risk thresholds and intervals without touching the final test repeatedly.
- Publish the model, metrics, drivers, and what-if only after passing the gate.

### After one month

- Add previous-day and previous-week baselines.
- Compare one global sequence model and one graph challenger under the same protocol.
- Improve uncertainty by capacity and demand regime.
- Add event data only when its historical publication time is reproducible.
- Treat rebalancing optimization as a downstream decision problem.

## 17. One-minute explanation

“I built an end-to-end system that predicts each Greater Taipei YouBike station's available bikes one hour ahead. Because the official feeds provide current state rather than a complete historical archive, the first task was a reliable five-minute collector with immutable R2 history, manifests, and cost controls. The dataset pairs each station with itself one hour later and uses only information known at prediction time. Seven models and three baselines compete on expanding future windows with a purge gap and one untouched final day. The system publishes only if the winner beats the same-as-now baseline. The product, API, Docker, documentation, and gates are complete; the final model score waits for the pre-declared five-day evidence window.”

