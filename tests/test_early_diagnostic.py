import pandas as pd
import pytest

from youbike_forecast.models.early import early_diagnostic_split


def test_early_diagnostic_uses_first_48_hours_then_untouched_day_three() -> None:
    timestamps = pd.Series(pd.date_range("2026-11-10", periods=73, freq="1h", tz="UTC"))
    split = early_diagnostic_split(timestamps)

    assert timestamps.loc[split.train_indices].max() == pd.Timestamp(
        "2026-11-11 23:00:00+00:00"
    )
    assert split.test_start == pd.Timestamp("2026-11-12 00:00:00+00:00")
    assert timestamps.loc[split.test_indices].min() == pd.Timestamp(
        "2026-11-12 01:00:00+00:00"
    )
    assert timestamps.loc[split.test_indices].max() == pd.Timestamp(
        "2026-11-13 00:00:00+00:00"
    )
    assert split.train_indices.intersection(split.test_indices).empty


def test_early_diagnostic_fails_closed_before_72_hours() -> None:
    timestamps = pd.Series(pd.date_range("2026-11-10", periods=72, freq="1h", tz="UTC"))

    with pytest.raises(ValueError, match="observed 71.00 hours; required 72"):
        early_diagnostic_split(timestamps)
