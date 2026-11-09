from __future__ import annotations

from datetime import UTC, datetime

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from youbike_forecast.collectors.client import NEW_TAIPEI_URL, TAIPEI_URL
from youbike_forecast.config import settings

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
    return {"status": "ok", "time": datetime.now(UTC).isoformat(), "model": "not-trained"}


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

