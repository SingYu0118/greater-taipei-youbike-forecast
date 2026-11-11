from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from youbike_forecast.pipeline.dataset import timestamp_from_path


def build_quality_report(
    raw_root: Path, log_path: Path | None = None, official_start_at: datetime | None = None
) -> dict[str, Any]:
    cloud_quality_path = raw_root.parent / "cloud_evidence" / "control" / "collection-quality.json"
    if cloud_quality_path.exists():
        return cloud_quality_report(cloud_quality_path)
    source_reports: dict[str, Any] = {}
    for source in ("taipei", "new_taipei", "weather_forecast"):
        files = sorted((raw_root / f"source={source}").glob("date=*/hour=*/*.json.gz"))
        retained_timestamps = [timestamp_from_path(path) for path in files]
        timestamps = (
            [timestamp for timestamp in retained_timestamps if timestamp >= official_start_at]
            if official_start_at is not None
            else []
        )
        report: dict[str, Any] = {
            "objects": len(timestamps),
            "retained_development_objects": len(retained_timestamps) - len(timestamps),
        }
        if timestamps:
            first = min(timestamps)
            last = max(timestamps)
            report.update(
                {
                    "first_fetched_at": first.isoformat(),
                    "last_fetched_at": last.isoformat(),
                    "coverage_hours": round((last - first).total_seconds() / 3600, 2),
                    "freshness_minutes": round(
                        max((datetime.now(UTC) - last).total_seconds(), 0) / 60, 2
                    ),
                }
            )
            cadence_minutes = 60 if source == "weather_forecast" else 5
            expected = max(
                int((last - first).total_seconds() // (cadence_minutes * 60)) + 1, 1
            )
            report["expected_objects"] = expected
            report["collection_completeness"] = round(min(len(timestamps) / expected, 1.0), 4)
        source_reports[source] = report
    run_summary = {"success": 0, "partial_failure": 0, "failure": 0, "malformed": 0}
    if official_start_at is not None and log_path and log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                started_at = datetime.fromisoformat(str(entry.get("started_at")))
                if started_at < official_start_at:
                    continue
                status = entry.get("status")
                if status in {"success", "partial_failure", "failure"}:
                    run_summary[status] += 1
                else:
                    run_summary["malformed"] += 1
            except (json.JSONDecodeError, TypeError, ValueError):
                run_summary["malformed"] += 1
    station_coverage_hours = min(
        source_reports[source].get("coverage_hours", 0)
        for source in ("taipei", "new_taipei")
    )
    station_completeness = min(
        source_reports[source].get("collection_completeness", 0)
        for source in ("taipei", "new_taipei")
    )
    minimum_five_days_met = station_coverage_hours >= 120
    collection_quality_met = station_completeness >= 0.95
    return {
        "authority": "local_launchagent",
        "generated_at": datetime.now(UTC).isoformat(),
        "sources": source_reports,
        "scheduler_runs": run_summary,
        "minimum_requirement": {
            "official_start_at": (
                official_start_at.isoformat() if official_start_at is not None else None
            ),
            "required_hours": 120,
            "observed_station_hours": station_coverage_hours,
            "minimum_completeness": 0.95,
            "observed_station_completeness": station_completeness,
            "five_days_met": minimum_five_days_met,
            "collection_quality_met": collection_quality_met,
        },
    }


def cloud_quality_report(path: Path) -> dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        sources = state["sources"]
        minimum_completeness = float(state["minimum_required_completeness"])
        observed_hours = float(state["observed_hours"])
        minimum_station_completeness = float(state["minimum_station_completeness"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid Cloudflare collection quality state: {path}") from error
    source_reports: dict[str, Any] = {}
    for source in ("taipei", "new_taipei", "weather_forecast"):
        item = sources[source]
        source_reports[source] = {
            "objects": int(item["objects"]),
            "expected_objects": int(item["expected_objects"]),
            "collection_completeness": float(item["completeness"]),
            "first_fetched_at": item.get("first_fetched_at"),
            "last_fetched_at": item.get("last_fetched_at"),
            "successes_since_tracking": int(item.get("successes_since_tracking", 0)),
            "failures_since_tracking": int(item.get("failures_since_tracking", 0)),
        }
    return {
        "authority": "cloudflare_r2",
        "generated_at": state["updated_at"],
        "reconstruction_basis": state.get("reconstruction_basis"),
        "sources": source_reports,
        "scheduler_runs": {
            "historical_manifests": int(state.get("historical_manifests", 0)),
            "tracked_runs": int(state.get("tracked_runs", 0)),
            "complete_since_tracking": int(state.get("complete_runs_since_tracking", 0)),
            "partial_failure_since_tracking": int(
                state.get("partial_failure_runs_since_tracking", 0)
            ),
        },
        "minimum_requirement": {
            "official_start_at": state["official_start_at"],
            "required_hours": float(state["required_hours"]),
            "observed_station_hours": observed_hours,
            "minimum_completeness": minimum_completeness,
            "observed_station_completeness": minimum_station_completeness,
            "five_days_met": bool(state["five_days_met"]),
            "collection_quality_met": bool(state["collection_quality_met"]),
        },
    }
