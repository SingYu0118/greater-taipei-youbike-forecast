# 72-Hour Preliminary Results

## Evidence boundary

The first official-window diagnostic completed on 2026-11-13. It used the first 48 hours for training, a 60-minute purge, and the third day as one untouched test shared by every candidate. The evaluation contains 1,919,352 training rows, 971,474 test rows, and 3,401 stations.

This result is `preliminary_not_for_production`. It does not replace the five-day rolling validation and final holdout.

## Ranking

| Rank | Candidate | MAE | RMSE | WAPE | Empty recall | Full recall |
|---:|---|---:|---:|---:|---:|---:|
| 1 | XGBoost | 2.547 | 4.314 | 27.40% | 34.82% | 6.96% |
| 2 | CatBoost | 2.559 | 4.444 | 27.53% | 45.91% | 11.67% |
| 3 | LightGBM | 2.567 | 4.452 | 27.62% | 46.14% | 10.88% |
| 4 | Histogram Gradient Boosting | 2.569 | 4.460 | 27.64% | 45.51% | 11.87% |
| 5 | Random Forest | 2.663 | 4.304 | 28.66% | 15.45% | 5.29% |
| 6 | Extra Trees | 2.666 | 4.324 | 28.69% | 13.60% | 3.82% |
| 7 | Persistence baseline | 2.777 | 4.976 | 29.88% | 65.26% | 43.39% |
| 8 | Ridge | 2.916 | 4.713 | 31.37% | 26.09% | 1.87% |
| 9 | Linear-trend baseline | 3.995 | 6.714 | 42.99% | 67.42% | 60.70% |
| 10 | Previous-hour baseline | 4.133 | 6.985 | 44.48% | 52.39% | 27.53% |

XGBoost improved MAE by **8.30%** relative to persistence on this one day. It fit in 22.99 seconds and predicted 971,474 rows in 0.83 seconds on the observed development machine.

## Interpretation

The diagnostic contains a positive signal: a learned model beat the strong same-as-now baseline on average bike-count error. However, XGBoost, CatBoost, LightGBM, and Histogram Gradient Boosting differ by only about 0.02 MAE, so one test day cannot establish a stable winner.

Risk detection remains weak. XGBoost has lower empty/full recall than persistence despite its better MAE. MAE rewards typical inventory accuracy and does not directly optimize rare boundary events. The formal report must retain both regression error and operational risk recall.

No model has been published. After five days, selection returns to the pre-declared three-fold validation and final holdout. Risk-threshold calibration or a separate risk classifier may later be evaluated using development folds only; the final holdout must not become a tuning set.

Source artifact: `artifacts/preliminary/early-72h-evaluation.json`.

