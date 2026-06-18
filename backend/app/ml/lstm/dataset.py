"""Labeled window dataset for the LSTM trajectory-anomaly model.

Builds training samples from the synthetic trajectory generator:
  * NORMAL trajectories  -> all windows labeled 0 (normal movement)
  * DEVIATING trajectories -> later-half windows labeled 1 (anomalous drift)

The LSTM learns to flag anomalous *movement patterns* from the sequence shape
alone — without knowing the planned route — complementing the geometric
route-deviation detector. Pure numpy (no torch).
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from app.ml.lstm.features import FEATURE_DIM, WINDOW, iter_windows
from scripts.synthetic import Scenario, generate_trajectory

# A few Bengaluru-area routes to vary the trajectories.
_ROUTES = [
    [(77.6090, 12.9750), (77.6030, 12.9755), (77.5980, 12.9758), (77.5950, 12.9760)],
    [(77.5750, 12.7980), (77.5780, 12.8010), (77.5810, 12.8040), (77.5840, 12.8070)],
    [(77.6245, 12.9352), (77.6280, 12.9400), (77.6320, 12.9450), (77.6360, 12.9500)],
    [(77.5720, 12.9770), (77.5760, 12.9740), (77.5800, 12.9710), (77.5840, 12.9680)],
]
_START = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def _points(pings) -> list[tuple[float, float, float]]:
    return [(p.lat, p.lon, p.recorded_at.timestamp()) for p in pings]


def build_dataset(n_per_combo: int = 120, *, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Return (X, y): X shape (N, WINDOW, FEATURE_DIM), y in {0,1}."""
    rng = np.random.default_rng(seed)
    X: list[np.ndarray] = []
    y: list[int] = []

    for i in range(n_per_combo):
        route = _ROUTES[i % len(_ROUTES)]
        s = int(rng.integers(0, 1_000_000))

        # Normal trajectory -> label 0 (all windows).
        normal = generate_trajectory(
            route, scenario=Scenario.NORMAL, n_points=30,
            start_time=_START, interval_s=60, seed=s,
        )
        for w in iter_windows(_points(normal)):
            X.append(w)
            y.append(0)

        # Deviating trajectory -> label 1 (later-half windows only).
        dev = generate_trajectory(
            route, scenario=Scenario.DEVIATING, n_points=30,
            start_time=_START, interval_s=60, seed=s + 1,
        )
        dev_windows = list(iter_windows(_points(dev)))
        cutoff = len(dev_windows) // 2
        for w in dev_windows[cutoff:]:
            X.append(w)
            y.append(1)

    Xarr = np.array(X, dtype=np.float32).reshape(-1, WINDOW, FEATURE_DIM)
    yarr = np.array(y, dtype=np.int64)
    return Xarr, yarr
