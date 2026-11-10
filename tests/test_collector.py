import pytest
import respx
from httpx import Response

from youbike_forecast.collectors.client import (
    NEW_TAIPEI_URL,
    TAIPEI_URL,
    Collector,
    PartialCollectionError,
)
from youbike_forecast.collectors.storage import LocalRawStorage
from youbike_forecast.config import Settings


@respx.mock
@pytest.mark.asyncio
async def test_partial_collection_preserves_successful_source(tmp_path) -> None:
    respx.get(TAIPEI_URL).mock(return_value=Response(503))
    respx.get(NEW_TAIPEI_URL, params={"page": 0, "size": 1000}).mock(
        return_value=Response(200, json=[{"sno": "n1"}])
    )
    collector = Collector(
        Settings(_env_file=None, data_dir=tmp_path, request_attempts=1),
        LocalRawStorage(tmp_path / "raw"),
    )
    with pytest.raises(PartialCollectionError) as captured:
        await collector.collect_all(include_weather=False)
    assert [result.source for result in captured.value.successful] == ["new_taipei"]
    assert len(list((tmp_path / "raw" / "source=new_taipei").glob("**/*.json.gz"))) == 1
