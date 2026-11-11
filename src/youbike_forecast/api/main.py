from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from youbike_forecast.collectors.client import NEW_TAIPEI_URL, TAIPEI_URL
from youbike_forecast.config import settings
from youbike_forecast.models.service import ForecastService, ModelUnavailableError
from youbike_forecast.pipeline.quality import build_quality_report

forecast_service = ForecastService(
    settings.model_dir,
    settings.formal_feature_path,
    settings.raw_dir,
    settings.data_dir / "logs" / "collector.jsonl",
    settings.collection_start_at,
)


class WhatIfRequest(BaseModel):
    source: Literal["taipei", "new_taipei"]
    precipitation: float | None = Field(None, ge=0, le=100)
    precipitation_probability: float | None = Field(None, ge=0, le=100)
    temperature_2m: float | None = Field(None, ge=-20, le=50)

app = FastAPI(
    title="Greater Taipei YouBike Forecast API",
    version="0.1.0",
    description="One-hour-ahead station availability forecasts and model explanations.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "time": datetime.now(UTC).isoformat(),
        "model": "ready" if forecast_service.is_ready() else "collecting-training-data",
    }


@app.get("/api/v1/forecasts/latest")
async def latest_forecasts() -> dict:
    try:
        forecasts = forecast_service.forecasts()
        model = forecast_service.metadata()
        as_of = max(forecast["observation_time"] for forecast in forecasts)
        return {
            "as_of": as_of,
            "count": len(forecasts),
            "model_status": "ready",
            "model": model,
            "stations": forecasts,
        }
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/model/metrics")
async def model_metrics() -> dict:
    try:
        return forecast_service.metrics()
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/model/drivers")
async def model_drivers() -> dict:
    try:
        return forecast_service.drivers()
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/data/quality")
async def data_quality() -> dict:
    return build_quality_report(
        settings.raw_dir,
        settings.data_dir / "logs" / "collector.jsonl",
        settings.collection_start_at,
    )


@app.post("/api/v1/stations/{station_id}/what-if")
async def station_what_if(station_id: str, request: WhatIfRequest) -> dict:
    field_mapping = {
        "precipitation": "forecast_precipitation",
        "precipitation_probability": "forecast_precipitation_probability",
        "temperature_2m": "forecast_temperature_2m",
    }
    values = request.model_dump(exclude_none=True)
    source = values.pop("source")
    overrides = {field_mapping[name]: value for name, value in values.items()}
    if not overrides:
        raise HTTPException(status_code=422, detail="At least one scenario value is required")
    try:
        return forecast_service.what_if(station_id, overrides, source)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Station not found") from exc


@app.get("/api/v1/stations/live")
async def live_stations(source: str = Query("all", pattern="^(all|taipei|new_taipei)$")) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            taipei = []
            new_taipei = []
            if source in {"all", "taipei"}:
                response = await client.get(TAIPEI_URL)
                response.raise_for_status()
                taipei = [
                    {
                        "source": "taipei",
                        "station_id": row["sno"],
                        "station_name": row["sna"].removeprefix("YouBike2.0_"),
                        "district": row.get("sarea"),
                        "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"]),
                        "capacity": int(row["Quantity"]),
                        "available_bikes": int(row["available_rent_bikes"]),
                        "available_docks": int(row["available_return_bikes"]),
                    }
                    for row in response.json()
                ]
            if source in {"all", "new_taipei"}:
                page = 0
                while True:
                    response = await client.get(
                        NEW_TAIPEI_URL,
                        params={"page": page, "size": settings.ntpc_page_size},
                    )
                    response.raise_for_status()
                    batch = response.json()
                    new_taipei.extend(
                        {
                            "source": "new_taipei",
                            "station_id": row["sno"],
                            "station_name": row["sna"].removeprefix("YouBike2.0_"),
                            "district": row.get("sarea"),
                            "latitude": float(row["lat"]),
                            "longitude": float(row["lng"]),
                            "capacity": int(row["tot_quantity"]),
                            "available_bikes": int(row["sbi_quantity"]),
                            "available_docks": int(row["bemp"]),
                        }
                        for row in batch
                    )
                    if len(batch) < settings.ntpc_page_size:
                        break
                    page += 1
            stations = taipei + new_taipei
            return {
                "as_of": datetime.now(UTC).isoformat(),
                "count": len(stations),
                "model_status": "collecting-training-data",
                "stations": stations,
            }
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="Official live feed unavailable") from exc

