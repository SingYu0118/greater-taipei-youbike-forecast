# Model Candidate Review

## Decision rule

A model enters the formal five-day competition only when it can:

1. produce a direct 60-minute-ahead prediction from information available at prediction time;
2. share information across approximately 3,400 stations;
3. use calendar, weather, location, and neighbouring-station covariates;
4. complete the identical purged expanding-window evaluation on commodity hardware; and
5. be serialized and served by the existing FastAPI inference path.

Adding algorithms that cannot satisfy those conditions would increase the model count without
creating a fair or operationally useful comparison.

## Included in the formal competition

| Family | Candidate | Reason for inclusion |
|---|---|---|
| Linear | Ridge | Stable, interpretable low-variance control. |
| Bagging | Random Forest | Conventional bootstrap-aggregated tree benchmark. |
| Randomized bagging | Extra Trees | Tests whether additional split randomization improves generalization and speed. |
| Boosting | Histogram Gradient Boosting | Dependency-light large-tabular-data benchmark with native missing-value routing. |
| Boosting | LightGBM | Efficient leaf-wise histogram boosting for structured data. |
| Boosting | XGBoost | Mature regularized histogram boosting with a different tree builder. |
| Boosting | CatBoost | Symmetric-tree boosting and a distinct regularization strategy. |

Every candidate sees the same features, training timestamps, purge gap, validation timestamps,
and untouched final holdout. Selection uses mean cross-validation MAE, with mean RMSE as the
tie-breaker. The winning family is then fitted once on all development data and scored once on
the final holdout.

The dependency group selects the official CPU-only XGBoost distribution on Linux and the
standard CPU-capable distribution on macOS. This avoids pulling GPU and collective-communication
libraries into the production container when the application never requests a GPU device.

## Reviewed but deferred

| Candidate | Current decision | Revisit condition |
|---|---|---|
| ARIMA | Defer | Use as a station-level diagnostic after several weeks of complete seasonal history. |
| ARIMAX/SARIMAX | Defer | Revisit when repeated weekly regimes justify thousands of rolling station-level fits. |
| LSTM/GRU | Defer | Revisit after at least one month; use a global model with station embeddings. |
| TFT, N-HiTS, TiDE, PatchTST | Defer | Revisit with longer history and a separate, leakage-audited sequence pipeline. |
| Graph neural networks | Defer | Revisit with longer history and a defensible station graph or origin-destination trips. |
| Prophet | Exclude for this target | Designed for longer-horizon trend and seasonality, not this short-horizon network state task. |
| k-nearest neighbours | Exclude at current scale | Prediction cost and memory grow poorly with millions of rows. |
| kernel SVR | Exclude at current scale | Training complexity is unsuitable for the expected row count. |
| exact Gradient Boosting | Exclude | Histogram boosting provides the relevant family comparison at much lower cost. |
| AdaBoost | Exclude | Adds a weaker tree-boosting variant without a distinct operational advantage here. |
| Elastic Net/Lasso | Exclude from final table | Ridge already supplies the linear control; station codes are not meaningfully sparse coefficients. |

## Probabilistic forecasts

Prediction uncertainty is handled separately from point-model selection. The production bundle
calibrates a capacity-bounded interval from out-of-fold absolute residuals. Quantile LightGBM or
distributional models can be compared after more history is available, but they should not be
counted as additional point-model families merely to inflate the candidate total.

## Neural-model follow-up

After one month, the recommended second-stage experiment is a global N-HiTS or TFT model, not
one neural network per station. It should use rolling-origin folds, known-future calendar and
weather inputs, observed-past station and neighbour states, station embeddings, and the same
final holdout used by the tabular challenger. It should be adopted only if the improvement
justifies its larger training, inference, and monitoring cost.
