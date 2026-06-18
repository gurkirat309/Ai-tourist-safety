"""Phase 4 tests for the LSTM trajectory-anomaly model.

The feature/dataset logic is pure numpy and always tested. The torch-dependent
inference is tested only if torch + a trained model are available; otherwise the
scorer must degrade gracefully to None.
"""

from datetime import UTC, datetime

import numpy as np

from app.ml.lstm.dataset import build_dataset
from app.ml.lstm.features import FEATURE_DIM, WINDOW, make_window, step_features
from app.ml.lstm.infer import score_trajectory
from scripts.synthetic import Scenario, generate_trajectory

ROUTE = [(77.609, 12.975), (77.603, 12.9755), (77.598, 12.9758), (77.595, 12.976)]
START = datetime(2026, 1, 1, 10, tzinfo=UTC)


def _pts(pings):
    return [(p.lat, p.lon, p.recorded_at.timestamp()) for p in pings]


def test_step_features_shape():
    pts = _pts(generate_trajectory(ROUTE, scenario=Scenario.NORMAL, n_points=10,
                                   start_time=START, seed=1))
    feats = step_features(pts)
    assert feats.shape == (9, FEATURE_DIM)  # n_points-1 steps
    assert np.isfinite(feats).all()


def test_make_window_shape_and_padding():
    # Short trajectory left-pads to WINDOW.
    short = _pts(generate_trajectory(ROUTE, scenario=Scenario.NORMAL, n_points=4,
                                     start_time=START, seed=1))
    w = make_window(short)
    assert w.shape == (WINDOW, FEATURE_DIM)


def test_normal_and_deviating_features_differ():
    normal = step_features(_pts(generate_trajectory(
        ROUTE, scenario=Scenario.NORMAL, n_points=30, start_time=START, seed=5)))
    dev = step_features(_pts(generate_trajectory(
        ROUTE, scenario=Scenario.DEVIATING, n_points=30, start_time=START, seed=5)))
    # The later-half movement features should differ meaningfully (the basis the
    # LSTM learns from); direction of difference is route-dependent.
    diff = np.abs(dev[15:].mean(axis=0) - normal[15:].mean(axis=0)).sum()
    assert diff > 1.0


def test_build_dataset_balanced_windows():
    X, y = build_dataset(n_per_combo=8, seed=0)
    assert X.ndim == 3 and X.shape[1:] == (WINDOW, FEATURE_DIM)
    assert set(np.unique(y)).issubset({0, 1})
    assert 0 < y.mean() < 1  # both classes present


def test_score_trajectory_is_graceful_or_valid():
    """Either returns None (no torch/model) or a probability in [0, 1]."""
    pts = _pts(generate_trajectory(ROUTE, scenario=Scenario.NORMAL, n_points=20,
                                   start_time=START, seed=2))
    score = score_trajectory(pts)
    assert score is None or (0.0 <= score <= 1.0)


def test_score_trajectory_separates_when_model_present():
    """If a trained model is available, deviating should score higher than normal."""
    normal = _pts(generate_trajectory(ROUTE, scenario=Scenario.NORMAL, n_points=30,
                                      start_time=START, seed=9))
    dev = _pts(generate_trajectory(ROUTE, scenario=Scenario.DEVIATING, n_points=30,
                                   start_time=START, seed=9))
    sn, sd = score_trajectory(normal), score_trajectory(dev)
    if sn is None or sd is None:
        import pytest

        pytest.skip("LSTM model/torch not available")
    assert sd > sn
