# API Contract

The FastAPI OpenAPI document is available at `/docs` when the backend is running.

## `GET /health`

Reports service time, health, and loaded model status. A model status of `collecting-training-data` is expected during the mandatory collection period and must not be presented as a forecast.

## `GET /api/v1/stations/live`

Query parameter:

- `source`: `all`, `taipei`, or `new_taipei`.

Response fields:

```json
{
  "as_of": "UTC timestamp",
  "count": 3446,
  "model_status": "collecting-training-data",
  "stations": [
    {
      "source": "taipei",
      "station_id": "500101001",
      "station_name": "MRT Technology Bldg. Sta.",
      "district": "Daan Dist.",
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

## Evidence-gated model endpoints

- `GET /api/v1/forecasts/latest`: latest forecast and bounded uncertainty range for every station, plus model ID, family, training time, code version, and interval-calibration method.
- `GET /api/v1/model/metrics`: every rolling fold, model comparison, baselines, and untouched final holdout.
- `GET /api/v1/model/drivers`: permutation importance, global SHAP values, and a local SHAP example.
- `POST /api/v1/stations/{station_id}/what-if`: controlled precipitation, rain-probability, or temperature scenario. The JSON body includes the required `source` (`taipei` or `new_taipei`) so station identity is unambiguous.
- `GET /api/v1/data/quality`: collection completeness, freshness, scheduler outcomes, and the 120-hour evidence gate.

Forecast and what-if endpoints return HTTP 503 until every publication gate passes: artifacts exist, final-holdout MAE beats persistence, the official collection window reaches 120 hours, and snapshot completeness reaches 95%. Evaluation and driver reports remain separately inspectable after training for audit. The service never substitutes synthetic or demo predictions. A what-if response is explicitly labelled as model behaviour rather than a causal estimate.

`GET /api/v1/data/quality` reports only the official evidence window. Until `COLLECTION_START_AT` is set, official coverage and scheduler counts remain zero; retained development snapshots are reported separately and do not advance the gate.

