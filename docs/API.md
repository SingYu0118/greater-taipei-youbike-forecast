# API Contract

The FastAPI OpenAPI document is available at `/docs` when the backend is running.

## `GET /health`

Reports service time, health, and model-serving status. The public deployment currently returns `model: ready` and `forecast_serving: snapshot` after the formal publication gate has passed.

## `GET /api/v1/stations/live`

Query parameter:

- `source`: `all`, `taipei`, or `new_taipei`.

Response fields:

```json
{
  "as_of": "UTC timestamp",
  "count": 3446,
  "model_status": "ready",
  "stations": [
    {
      "source": "taipei",
      "station_id": "500101001",
      "station_name": "捷運科技大樓站",
      "station_name_en": "MRT Technology Bldg. Sta.",
      "district": "大安區",
      "district_en": "Daan Dist.",
      "latitude": 25.02605,
      "longitude": 121.5436,
      "capacity": 28,
      "available_bikes": 1,
      "available_docks": 27
    }
  ]
}
```

The endpoint returns HTTP 502 with a generic message when an official source is unavailable. Upstream details remain in server logs.

Official `snaen` and `sareaen` values populate the English station and district fields. The client
searches both languages and renders `Chinese name (English name)` when both are available.

## Evidence-gated model endpoints

- `GET /api/v1/forecasts/latest`: latest forecast and bounded uncertainty range for every station, plus model ID, family, training time, code version, and interval-calibration method.
- `GET /api/v1/model/metrics`: every rolling fold, model comparison, baselines, and untouched final holdout.
- `GET /api/v1/model/drivers`: permutation importance, global SHAP values, and a local SHAP example.
- `POST /api/v1/stations/{station_id}/what-if`: controlled precipitation, rain-probability, or temperature scenario. The JSON body includes the required `source` (`taipei` or `new_taipei`) so station identity is unambiguous.
- `GET /api/v1/data/quality`: collection completeness, freshness, scheduler outcomes, and the 120-hour evidence gate.

The publication gate has passed for model `catboost-20261115T150527Z`. The public Worker reads `control/latest-forecasts.json` from R2 and serves the versioned station snapshot without loading the Python model in the edge isolate. `GET /api/v1/forecasts/latest` returns HTTP 503 only when that published object is missing or malformed. Evaluation and driver reports remain separately inspectable for audit. The service never substitutes synthetic or demo predictions. A what-if response is explicitly labelled as model behaviour rather than a causal estimate.

`GET /api/v1/data/quality` reports only the official evidence window. Retained development snapshots are reported separately and never advance the completed formal gate.

