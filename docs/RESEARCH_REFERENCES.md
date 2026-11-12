# Research References and Design Lessons

This review records how public repositories and primary research changed the system design. A
reference is included only when it informs the target, feature contract, validation, model
competition, or operational roadmap. Similar-looking studies that predict trip demand rather than
station inventory are labelled explicitly.

## What changed after the review

| Evidence from prior work | Decision in this project | Status |
|---|---|---|
| Station inventory is a bounded state, and empty and full stations are separate service failures. | Predict `available_bikes(t+60)` directly, clip predictions to `[0, capacity]`, and report empty/full risk separately. | Adopted |
| A 60-minute horizon gives an operator time to route a rebalancing vehicle while retaining useful station-level precision. | Keep one direct 60-minute target rather than optimizing a shorter horizon after seeing results. | Adopted |
| Current inventory is usually a strong short-horizon predictor. Simple dynamic models can match or beat more complex learners. | Persistence is a publication gate, not a weak baseline included only for comparison. | Adopted |
| Time, weather, station identity, and recent movement repeatedly appear as useful inputs. Spatial models add value when nearby stations interact. | Use issue-time weather, calendar, lags, rolling statistics, MRT distance, and neighbour inventory under one information-availability contract. | Adopted |
| Arrival and departure models can derive future inventory from net flow. They require reliable trip or flow observations. | Keep direct inventory prediction for version one because public Greater Taipei inputs contain snapshots, not complete trip flows. | Deferred |
| Graph attention and recurrent models can learn spatial and temporal dependence but need repeated regimes and more history. | Use lightweight neighbour features during the five-day gate. Revisit one global graph or sequence challenger after one month. | Deferred |
| Forecast accuracy and rebalancing value are different evaluation layers. | Keep forecasting as the current scope. Treat routing, incentives, and inventory optimization as downstream work. | Deferred |

## Repository review

### Public data reuse decision

| Source | Material found in the repository | Can we use it? | Decision |
|---|---|---|---|
| `tses89214/youbike-historical-data` | Daily Taipei snapshot CSV files with publisher timestamps. | Yes, for development practice. | Already isolated under the practice pipeline. It can exercise feature building and early day-three tests, but never replaces the formal collector window. |
| `aaron1aaron2/GMAN-based-Forecasting-of-YouBike-Shortages-in-Taiwan` | 5,181 raw ten-minute JSON snapshots from 4 December 2021 through 8 January 2022, plus a station matrix, station map and graph edges. The sample feed is the legacy Taipei YouBike schema. | Yes, as a legacy benchmark or graph-model sandbox. | Do not merge it into the formal dataset: it is Taipei-only, several years old, uses the former station network, and does not provide New Taipei coverage or our collector receive time. Preserve its MIT notice if code or packaged material is redistributed. |
| `joeycyhuang/bss-inventory-rebalancing` | Small derived files: station conditions cover approximately 1--5 April 2023; the repository also contains trip aggregates and optimization outputs. Its README describes a separate May--August 2024 government dataset. | Only as a method example. | The checked-in files do not reproduce the described four-month source dataset, and no repository licence was found. Do not import them into training. |
| `taipei-doit/YouBike-Optimization` | Modeling code and placeholder input directories for transport, land-use, population and transaction inputs. | No direct training history. | Reuse the feature and model ideas only. The repository does not publish the raw operational inputs needed to recreate its results. |

These repositories are useful for pre-production experiments, but they cannot satisfy the
assignment's five-day collection requirement. Formal metrics continue to use only snapshots
received by this project's collector after the declared collection start.

### Direct YouBike references

| Repository | What it demonstrates | What we use | Evidence boundary |
|---|---|---|---|
| [aaron1aaron2/GMAN-based-Forecasting-of-YouBike-Shortages-in-Taiwan](https://github.com/aaron1aaron2/GMAN-based-Forecasting-of-YouBike-Shortages-in-Taiwan) | Taipei inventory collection at ten-minute intervals and graph-based inventory forecasting. | Motivation for spatial features and the one-month graph-model roadmap. | The default example predicts one ten-minute step, uses an older PyTorch stack, and does not document our required purged rolling validation. |
| [tses89214/youbike-historical-data](https://github.com/tses89214/youbike-historical-data) | Public daily Taipei station-inventory CSV files built from repeated live-feed polling. | Development-only practice importer and early pipeline diagnostics. | Taipei only; publisher `infoTime` replaces unavailable collector fetch time; never formal evidence. |
| [taipei-doit/YouBike-Optimization](https://github.com/taipei-doit/YouBike-Optimization) | Officially supported hourly rental/return demand modeling with LightGBM, XGBoost, and CatBoost over spatial grids. | Supports the use of global tabular boosting and transport/geographic context. | Predicts grid demand and future station potential, not the exact future station inventory target. |
| [joeycyhuang/bss-inventory-rebalancing](https://github.com/joeycyhuang/bss-inventory-rebalancing) | Taipei inventory rebalancing and vehicle-routing work using station, transaction, and dispatch records. | Downstream operational roadmap after a forecast passes publication gates. | Its described source records are not a reproducible substitute for the assignment's public collector. |

### Transferable system references

| Repository | Relevant lesson | Project response |
|---|---|---|
| [dssg/bikeshare](https://github.com/dssg/bikeshare) | Predicts 60-minute arrivals and departures, converts net flow into future inventory, and connects collection, modeling, validation, and a map application. | Retain the 60-minute operational framing and end-to-end architecture; defer the net-flow target until reliable trip flows exist. |
| [danielazamorah/citibike-stations-ml](https://github.com/danielazamorah/citibike-stations-ml) | Treats bike and dock availability as bounded station-level outputs and packages training behind a cloud API. | Preserve capacity bounds and explicit serving contracts; do not copy its calendar-only target formulation or reported proof-of-concept performance. |
| [rishi-kumar0208/divvy-bike-rebalancing](https://github.com/rishi-kumar0208/divvy-bike-rebalancing) | Builds lagged features with a chronological train/test split and separates forecasting from network-flow optimization. | Reinforces past-only features, an untouched future test, and a separate optimization layer. |

## Primary research

1. Almannaa, M. H., Elhenawy, M., and Rakha, H. A. (2020). [Dynamic linear
   models to predict bike availability in a bike sharing
   system](https://doi.org/10.1080/15568318.2019.1611976). The paper evaluates bike-count
   prediction at 15, 30, 45, 60, and 120 minutes and shows why simple dynamic models remain
   credible challengers.
2. Zheng, C., Fan, X., Wang, C., and Qi, J. (2020). [GMAN: A Graph Multi-Attention
   Network for Traffic Prediction](https://doi.org/10.1609/aaai.v34i01.5477). GMAN motivates a
   future spatial-temporal challenger but does not remove the need for a common leakage-safe
   evaluation protocol.
3. Juan, Y.-C. et al. (2024). [Enhancing Youbike Redistribution System: A Study on Station
   Recommendation Using a Genetic Algorithm](https://doi.org/10.3390/proceedings2024110035).
   This Taipei study links demand prediction, weather, crowd context, station clustering, and
   downstream rebalancing. Its detailed data require formal access and are not publicly
   reproducible from the live feed.
4. Nejadshamsi, S. et al. (2026). [Predicting Short-Term Bike-Sharing Demand at Station
   Level: A Multi-Task Dynamic Graph-Based Spatiotemporal
   Approach](https://doi.org/10.1016/j.knosys.2025.114986). The work explains why one hour is
   operationally meaningful and why check-in and check-out relationships matter.
5. Hulot, P. et al. (2024). [Dynamic Rebalancing for Bike-Sharing Systems under Inventory
   Interval and Target Predictions](https://doi.org/10.1016/j.ejtl.2024.100147). This work
   separates demand prediction, inventory targets, and the rebalancing decision.

## Interpretation rules

- Repository metrics are not copied into this project's result table because datasets, targets,
  horizons, and splits differ.
- A paper supporting a model family does not qualify that family for the five-day competition.
- Every new challenger must use the same issue-time features, purge gap, folds, final holdout, and
  persistence gate.
- Practice-history results remain development evidence even when the source repository is public.
- Forecast explanations describe model behaviour, not causal effects or guaranteed operational
  savings.

Last reviewed: 2026-11-12.
