# Final Five-Day Model Results

## Result status

The formal model competition completed on 2026-11-15 using only immutable observations collected after the declared official start. The evaluation covers **4,858,440 labelled rows** from **3,401 stations** across Taipei and New Taipei.

The publication gate passed. CatBoost achieved lower MAE than persistence on the untouched final holdout. The public application now displays a versioned R2 batch snapshot containing station-level forecasts, empirical uncertainty bounds, and weather what-if outputs. The forecast origin time is shown explicitly; the application does not claim that CatBoost runs natively inside the free Cloudflare Worker.

## Leakage-safe evaluation

Model selection and final assessment use different future periods:

1. The latest 24 hours are removed before model comparison.
2. Seven learned candidates compete on three expanding validation folds.
3. Each fold uses a 12-hour future validation window and a 60-minute purge gap.
4. Mean cross-validation MAE selects the model family; mean RMSE breaks ties.
5. The selected model is fitted on the complete development period and evaluated once on the untouched 24-hour holdout.

The final holdout contains **976,209 rows**. No holdout metric was used to select CatBoost.

## Cross-validation model ranking

| Rank | Model | Mean CV MAE | Mean CV RMSE |
|---:|---|---:|---:|
| 1 | CatBoost | **2.609** | 4.357 |
| 2 | XGBoost | 2.611 | **4.270** |
| 3 | LightGBM | 2.628 | 4.389 |
| 4 | Histogram Gradient Boosting | 2.641 | 4.418 |
| 5 | Extra Trees | 2.753 | 4.311 |
| 6 | Random Forest | 2.769 | 4.317 |
| 7 | Ridge | 2.938 | 4.581 |

CatBoost and XGBoost are effectively close on average MAE. CatBoost wins under the pre-declared rule by 0.0017 bikes. This small margin is a reason to keep monitoring model ranking as more weeks arrive.

## Untouched final holdout

| Metric | CatBoost | Persistence | Relative improvement |
|---|---:|---:|---:|
| MAE | **2.026 bikes** | 2.056 bikes | **1.48%** |
| RMSE | **3.500 bikes** | 3.701 bikes | **5.41%** |
| WAPE | **18.24%** | 18.51% | **1.48%** |
| Empty-risk recall | 35.24% | **62.76%** | Lower |
| Full-risk recall | 20.66% | **53.84%** | Lower |

The learned model improves average inventory error and reduces large misses, but persistence remains much stronger at detecting boundary events. The correct conclusion is narrow: CatBoost passes the regression publication gate, while empty/full alerts still require a separate threshold or classification objective.

## Segment checks

- New Taipei MAE: **1.889 bikes** across 459,648 holdout rows.
- Taipei MAE: **2.148 bikes** across 516,561 holdout rows.
- Rain-period MAE: **1.915 bikes**; dry-period MAE: **2.167 bikes**.
- Large-station MAE: **3.256 bikes** versus 1.432 for small stations. WAPE is lower for large stations because their inventories are larger.
- The holdout is a weekend period, so weekday generalization relies on the rolling folds and remains an important monitoring item.

## What drives the model

Global SHAP importance on a fixed holdout sample ranks the current station state first:

1. Current available bikes
2. Neighbouring-station bike ratio
3. Five-minute bike lag
4. Station capacity
5. Fifteen-minute bike lag
6. Recent 60-minute variability
7. Time of day
8. Recent 60-minute mean
9. Available docks
10. Distance to the nearest MRT station

Weather variables contribute less than current inventory and recent movement during this five-day window. That does not establish a causal or permanent ordering. The short sample contains limited weather and calendar regimes.

## Artifact and reproducibility

- Model ID: `catboost-20261115T150527Z`
- Code version: `d2ce8c27f02cc59a128d824b93bffd2d26a4254e`
- Model bundle: `artifacts/models/model.joblib`
- Evaluation report: `artifacts/models/evaluation.json`
- Driver report: `artifacts/models/drivers.json`
- Uncertainty calibration: 90th percentile of rolling-validation out-of-fold absolute errors

Rebuild the formal result with:

```bash
make sync-r2
make dataset
make features
make train
```

## Limits and next month

Five days satisfy the assignment but do not cover repeated weekly seasonality, major events, school schedules, or varied weather. With another month, the next experiments should add day/week seasonal baselines, tune a separate empty/full risk model, recalibrate intervals by station size and time regime, and reassess sequence or graph models only after repeated weekly patterns exist.
