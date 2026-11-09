# API Contract

The FastAPI OpenAPI document is available at `/docs` when the backend is running.

## `GET /health`

Reports service time, health, and loaded model status. A model status of `not-trained` is expected during the mandatory collection period and must not be presented as a forecast.

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

## Planned endpoints after model evidence gate

- `GET /api/v1/forecasts/latest`: all current station forecasts and uncertainty ranges.
- `GET /api/v1/stations/{station_id}/history`: recent observed and predicted series.
- `GET /api/v1/stations/{station_id}/explanation`: local SHAP drivers.
- `POST /api/v1/stations/{station_id}/what-if`: controlled weather scenario.
- `GET /api/v1/model/metrics`: baselines, folds, final holdout, and subgroup metrics.
- `GET /api/v1/data/quality`: collection completeness and freshness.

