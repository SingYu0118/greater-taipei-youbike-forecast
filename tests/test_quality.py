import json
from datetime import UTC, datetime, timedelta

from youbike_forecast.collectors.storage import LocalRawStorage
from youbike_forecast.pipeline.quality import build_quality_report


def test_quality_report_calculates_coverage_and_gate(tmp_path) -> None:
    raw_root = tmp_path / "raw"
    storage = LocalRawStorage(raw_root)
    start = datetime(2026, 11, 1, tzinfo=UTC)
    for source in ("taipei", "new_taipei"):
        storage.put_json(source, start, [{"source": source}])
        storage.put_json(source, start + timedelta(hours=120), [{"source": source}])
    storage.put_json("weather_forecast", start, {"locations": []})
    report = build_quality_report(raw_root, official_start_at=start)
    assert report["minimum_requirement"]["five_days_met"] is True
    assert report["minimum_requirement"]["observed_station_hours"] == 120
    assert report["sources"]["taipei"]["objects"] == 2
    assert report["sources"]["taipei"]["collection_completeness"] < 0.01


def test_quality_report_does_not_start_clock_without_official_timestamp(tmp_path) -> None:
    raw_root = tmp_path / "raw"
    storage = LocalRawStorage(raw_root)
    storage.put_json("taipei", datetime(2026, 11, 1, tzinfo=UTC), [{}])
    report = build_quality_report(raw_root)
    assert report["minimum_requirement"]["official_start_at"] is None
    assert report["minimum_requirement"]["observed_station_hours"] == 0
    assert report["sources"]["taipei"]["objects"] == 0
    assert report["sources"]["taipei"]["retained_development_objects"] == 1


def test_quality_report_excludes_development_snapshots_before_official_start(tmp_path) -> None:
    raw_root = tmp_path / "raw"
    storage = LocalRawStorage(raw_root)
    development = datetime(2026, 11, 1, tzinfo=UTC)
    official = development + timedelta(days=1)
    for source in ("taipei", "new_taipei"):
        storage.put_json(source, development, [{"source": source}])
        storage.put_json(source, official, [{"source": source}])
    report = build_quality_report(raw_root, official_start_at=official)
    assert report["sources"]["taipei"]["objects"] == 1
    assert report["sources"]["taipei"]["coverage_hours"] == 0
    assert report["minimum_requirement"]["official_start_at"] == official.isoformat()


def test_quality_report_prefers_synced_cloudflare_authority(tmp_path) -> None:
    quality_path = tmp_path / "cloud_evidence" / "control" / "collection-quality.json"
    quality_path.parent.mkdir(parents=True)
    quality_path.write_text(
        json.dumps(
            {
                "official_start_at": "2026-11-10T07:51:49Z",
                "updated_at": "2026-11-11T02:40:57Z",
                "reconstruction_basis": "R2 object keys",
                "historical_manifests": 214,
                "tracked_runs": 3,
                "complete_runs_since_tracking": 3,
                "partial_failure_runs_since_tracking": 0,
                "observed_hours": 18.82,
                "required_hours": 120,
                "five_days_met": False,
                "minimum_station_completeness": 0.9513,
                "minimum_required_completeness": 0.95,
                "collection_quality_met": False,
                "sources": {
                    source: {
                        "objects": 215,
                        "expected_objects": 226,
                        "completeness": 0.9513,
                        "first_fetched_at": "2026-11-10T08:50:56Z",
                        "last_fetched_at": "2026-11-11T02:40:57Z",
                        "successes_since_tracking": 3,
                        "failures_since_tracking": 0,
                    }
                    for source in ("taipei", "new_taipei", "weather_forecast")
                },
            }
        ),
        encoding="utf-8",
    )
    report = build_quality_report(tmp_path / "raw")
    assert report["authority"] == "cloudflare_r2"
    assert report["minimum_requirement"]["observed_station_completeness"] == 0.9513
    assert report["scheduler_runs"]["historical_manifests"] == 214
