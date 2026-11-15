import httpx
import pytest
import respx
from httpx import Response

from youbike_forecast.api import main as api_main
from youbike_forecast.collectors.client import NEW_TAIPEI_URL, TAIPEI_URL

app = api_main.app


@respx.mock
@pytest.mark.asyncio
async def test_live_station_contract() -> None:
    respx.get(TAIPEI_URL).mock(
        return_value=Response(
            200,
            json=[
                {
                    "sno": "t1",
                    "sna": "YouBike2.0_Taipei station",
                    "sarea": "Daan",
                    "latitude": 25.0,
                    "longitude": 121.5,
                    "Quantity": 20,
                    "available_rent_bikes": 7,
                    "available_return_bikes": 13,
                }
            ],
        )
    )
    respx.get(NEW_TAIPEI_URL, params={"page": 0, "size": 1000}).mock(
        return_value=Response(
            200,
            json=[
                {
                    "sno": "n1",
                    "sna": "YouBike2.0_New Taipei station",
                    "sarea": "Banqiao",
                    "lat": "25.01",
                    "lng": "121.46",
                    "tot_quantity": "30",
                    "sbi_quantity": "11",
                    "bemp": "19",
                }
            ],
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/stations/live")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["stations"][0]["station_name"] == "Taipei station"
    assert body["stations"][1]["available_bikes"] == 11


@respx.mock
@pytest.mark.asyncio
async def test_live_station_maps_upstream_failure_to_502() -> None:
    respx.get(TAIPEI_URL).mock(return_value=Response(503))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/stations/live?source=taipei")
    assert response.status_code == 502
    assert response.json() == {"detail": "Official live feed unavailable"}


@pytest.mark.asyncio
async def test_forecasts_return_503_before_model_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_main.forecast_service, "model_dir", tmp_path / "missing-model")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/forecasts/latest")
    assert response.status_code == 503
    assert "not available" in response.json()["detail"]


@pytest.mark.asyncio
async def test_drivers_return_503_before_model_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_main.forecast_service, "model_dir", tmp_path / "missing-model")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/model/drivers")
    assert response.status_code == 503
    assert "not available" in response.json()["detail"]


@pytest.mark.asyncio
async def test_what_if_requires_source_and_scenario_value() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        missing_source = await client.post(
            "/api/v1/stations/example/what-if", json={"precipitation": 2}
        )
        missing_scenario = await client.post(
            "/api/v1/stations/example/what-if", json={"source": "taipei"}
        )
    assert missing_source.status_code == 422
    assert missing_scenario.status_code == 422

