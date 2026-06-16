"""M3 tests for the Bengaluru area-risk model (no DB / no network)."""

from datetime import UTC, datetime

import pytest

from app.ml.bengaluru_priors import (
    cell_center,
    cell_index,
    grid_shape,
    spatial_intensity,
    temporal_multiplier,
)
from app.ml.dataset import build_dataset
from app.ml.features import FEATURE_NAMES, build_features, features_to_row
from app.ml.risk_model import predict_risk, train_model

# Coordinates of seeded zones.
MAJESTIC = (12.9770, 77.5720)  # high-risk
CUBBON = (12.9760, 77.5950)  # low-risk


def test_grid_roundtrip():
    n_rows, n_cols = grid_shape()
    assert n_rows > 0 and n_cols > 0
    # A point maps to a cell whose centre maps back to the same cell.
    r, c = cell_index(*MAJESTIC)
    lat, lon = cell_center(r, c)
    assert cell_index(lat, lon) == (r, c)


def test_spatial_intensity_orders_zones():
    # Majestic (high prior) should exceed Cubbon Park (low prior).
    assert spatial_intensity(*MAJESTIC) > spatial_intensity(*CUBBON)


def test_temporal_multiplier_night_gt_day():
    # Saturday 22:00 should exceed Tuesday 10:00.
    sat_night = temporal_multiplier(22, 5)
    tue_day = temporal_multiplier(10, 1)
    assert sat_night > tue_day


def test_features_shape_and_order():
    feats = build_features(*MAJESTIC, datetime(2026, 6, 20, 22, tzinfo=UTC), 3.0)
    row = features_to_row(feats)
    assert len(row) == len(FEATURE_NAMES)
    assert set(feats.keys()) == set(FEATURE_NAMES)
    assert feats["is_night"] == 1.0
    assert feats["is_weekend"] == 1.0


def test_dataset_builds_with_positives():
    data = build_dataset(n_days=20, n_samples=4000, seed=1)
    assert list(data.frame.columns) == [*FEATURE_NAMES, "label"]
    assert len(data.frame) == 4000
    # Should contain both classes.
    assert 0 < data.frame["label"].mean() < 1
    # One baseline value per grid cell.
    n_rows, n_cols = grid_shape()
    assert len(data.cell_baseline) == n_rows * n_cols


@pytest.fixture(scope="module")
def trained_bundle():
    # Enough data for the learned structure to be stable (module-scoped: trained
    # once for all tests in this file).
    data = build_dataset(n_days=90, n_samples=40_000, seed=3)
    return train_model(data, seed=3).bundle


def _mean_risk(bundle, lat, lon, hours, dows):
    """Mean predicted risk over a set of hours/days at a fixed location."""
    vals = []
    for d in dows:
        for h in hours:
            # 2026-06-15 is a Monday, so day = 15 + dow lands on the right weekday.
            vals.append(
                predict_risk(lat, lon, datetime(2026, 6, 15 + d, h, tzinfo=UTC),
                             bundle=bundle)
            )
    return sum(vals) / len(vals)


def test_predict_in_unit_interval(trained_bundle):
    p = predict_risk(*MAJESTIC, datetime(2026, 6, 20, 22, tzinfo=UTC),
                     bundle=trained_bundle)
    assert 0.0 <= p <= 1.0


def test_predict_high_zone_gt_low_zone(trained_bundle):
    # Averaged across times so the comparison reflects spatial structure.
    hours, dows = range(0, 24, 3), range(7)
    high = _mean_risk(trained_bundle, *MAJESTIC, hours, dows)
    low = _mean_risk(trained_bundle, *CUBBON, hours, dows)
    assert high > low


def test_predict_night_gt_day_high_zone(trained_bundle):
    # Averaged across the week at the high-risk zone.
    night = _mean_risk(trained_bundle, *MAJESTIC, [21, 22, 23, 0], range(7))
    day = _mean_risk(trained_bundle, *MAJESTIC, [9, 10, 11, 12], range(7))
    assert night > day
