# Modeling and Time Validation

## 1. Objective

Predict `available_bikes(t + 60 minutes)` for each active station. Predictions are clipped to the physical range from zero to station capacity.

## 2. Why random splitting is invalid

Rows five minutes apart share nearly identical inventory and rolling features. A random row split would place near-duplicate future observations in training and validation, substantially overstating real deployment performance. All splits therefore use complete time ranges shared by every station.

## 3. Final holdout

The last 24 hours are removed before any model comparison or tuning. This period is evaluated once, after the winning model family and settings are selected. The holdout provides the closest available simulation of a new production day.

## 4. Expanding-window backtest

The development period uses three folds. Each validation window is 12 hours. The training set expands chronologically, and a 60-minute gap separates the last training observation from the first validation observation.

```text
Fold 1: [ training ---------------- ] [60m gap] [12h validation]
Fold 2: [ training expands ------------------ ] [gap] [12h validation]
Fold 3: [ training expands further ------------------- ] [gap] [12h validation]
Final : [ all development data ----------------------- ] [24h untouched test]
```

The purge gap prevents a label at the end of training from reaching into the validation period.

## 5. Competitors

### Baselines

- Persistence: future bikes equal current bikes.
- Linear trend: extrapolate the most recent 30-minute movement.
- Previous hour: use the station count observed one hour earlier.
- Previous day and previous week will be enabled only when enough history exists.

### Learned models

- Ridge regression: interpretable linear reference with median imputation and scaling.
- Random Forest: conventional bootstrap-aggregated tree reference.
- Extra Trees: nonlinear bagged-tree comparison.
- Histogram Gradient Boosting: dependency-light histogram booster designed for large tabular datasets.
- LightGBM: gradient boosting optimized for structured tabular data.
- XGBoost: mature histogram-based gradient boosting comparison.
- CatBoost: a second boosting family with different regularization and tree construction.

These seven candidates cover a linear control, two bagged-tree methods, and four distinct
gradient-boosting implementations. Standard Gradient Boosting is excluded because its exact
split search scales poorly at this row count and is superseded here by the histogram variant.
ARIMA/ARIMAX are not part of the five-day global competition: a defensible rolling-origin
comparison would require thousands of station-level models and repeated re-fitting, while the
current task needs one deployable global model that shares information across stations and uses
spatial covariates. LSTM, TFT, N-HiTS, and other neural sequence models are deferred until at
least one month of history provides repeated weekly and weather regimes.

Hyperparameter search, if enabled, is restricted to the development folds. Model selection uses mean cross-validation MAE, then RMSE as a tie-breaker. Fold-to-fold stability, inference latency, and empty/full risk recall are also reported.

The bagged-tree candidates use bounded depth and minimum leaf sizes so their memory footprint
remains defensible at the expected multi-million-row scale. Every fold records fit time,
prediction time, and prediction throughput; these operational measurements are reported but do
not override the pre-declared MAE/RMSE selection rule.

## 6. Metrics

| Metric | Use |
|---|---|
| MAE | Primary metric; directly interpretable as average bikes missed. |
| RMSE | Penalizes rare large misses. |
| WAPE | Normalizes aggregate absolute error by observed demand. |
| Empty recall | Fraction of actual `<=2 bikes` cases warned by the model. |
| Full recall | Fraction of actual `<=2 docks` cases warned by the model. |

Results are segmented by city, district, station capacity, hour, weekday/weekend, rain, and risk class to prevent a strong global average from hiding operational failures.

## 7. Prediction intervals

The model bundle stores the 90th percentile of absolute out-of-fold errors from the winning model's rolling validation windows. This calibration never uses the final holdout. The application displays a capacity-bounded interval, not a false point estimate alone. With more history, intervals should be calibrated separately by horizon, capacity band, and demand regime.

## 8. Explainability

- Permutation importance measures the out-of-time holdout score change when a feature is shuffled.
- Global SHAP importance identifies the features used across sampled holdout predictions.
- Local SHAP values explain one station forecast.
- Accumulated local effects or carefully constrained partial dependence shows nonlinear response patterns.
- A rain what-if changes only forecast weather inputs while holding station state and time fixed.

These are model-response explanations, not causal claims.

## 9. Minimum evidence gate

No model is labelled production-ready until it:

1. uses at least five complete days of station history;
2. beats persistence on final-holdout MAE;
3. reports all folds and the untouched final test;
4. passes feature-availability and target-alignment checks;
5. exposes its training coverage and model version in the API.

The serving layer enforces these gates. A model artifact alone is insufficient: the evaluation report must show lower final-holdout MAE than persistence, and the official collection window must reach 120 hours with at least 95% snapshot completeness. Otherwise forecast routes return HTTP 503.

