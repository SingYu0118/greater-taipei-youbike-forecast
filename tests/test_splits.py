from datetime import timedelta

import pandas as pd

from youbike_forecast.models.splits import expanding_time_folds, final_holdout_mask


def test_expanding_folds_are_ordered_and_purged() -> None:
    timestamps = pd.Series(pd.date_range("2026-11-01", periods=120, freq="h", tz="UTC"))
    train_mask, test_mask = final_holdout_mask(timestamps, holdout_hours=24)
    assert train_mask.sum() == 96
    assert test_mask.sum() == 24
    folds = expanding_time_folds(timestamps[train_mask], folds=3, validation_hours=12)
    assert len(folds) == 3
    for fold in folds:
        assert fold.train_end < fold.validation_start
        assert fold.validation_start - fold.train_end == timedelta(minutes=60)
        assert timestamps.loc[fold.train_indices].max() <= fold.train_end
        assert timestamps.loc[fold.validation_indices].min() > fold.validation_start

