"""Trajectory feature extraction for the LSTM anomaly model (pure numpy).

A trajectory is a time-ordered list of (lat, lon, t_seconds). For each step
between consecutive points we compute 4 movement features:

  * dist_m  — geodesic step length (haversine)
  * speed   — dist / time gap (m/s)
  * turn    — absolute heading change vs the previous segment (radians)
  * dt_s    — time gap (s)

The model consumes a fixed-length **window** of the most recent steps. Features
are scaled to ~O(1) by fixed constants (kept here so training and serving match).
No torch here — this module is always importable and unit-tested.
"""

from __future__ import annotations

import math

import numpy as np

WINDOW = 8          # number of steps fed to the LSTM
FEATURE_DIM = 4
# Scaling constants (rough urban-walking magnitudes) to normalise features.
_SCALE = np.array([50.0, 5.0, math.pi, 120.0], dtype=np.float32)
_EARTH_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return _EARTH_M * 2 * math.asin(math.sqrt(a))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.atan2(x, y)


def step_features(points: list[tuple[float, float, float]]) -> np.ndarray:
    """Raw per-step features for a trajectory. Shape (n_steps, 4)."""
    if len(points) < 2:
        return np.zeros((0, FEATURE_DIM), dtype=np.float32)
    rows = []
    prev_bearing = None
    for i in range(1, len(points)):
        lat1, lon1, t1 = points[i - 1]
        lat2, lon2, t2 = points[i]
        dist = haversine_m(lat1, lon1, lat2, lon2)
        dt = max(1e-3, t2 - t1)
        speed = dist / dt
        b = _bearing(lat1, lon1, lat2, lon2)
        if prev_bearing is None:
            turn = 0.0
        else:
            diff = abs(b - prev_bearing) % (2 * math.pi)
            turn = min(diff, 2 * math.pi - diff)
        prev_bearing = b
        rows.append([dist, speed, turn, dt])
    return np.array(rows, dtype=np.float32)


def _normalise(steps: np.ndarray) -> np.ndarray:
    return np.clip(steps / _SCALE, 0.0, 4.0)


def make_window(points: list[tuple[float, float, float]], window: int = WINDOW) -> np.ndarray:
    """Most-recent `window` steps, normalised + left-padded. Shape (window, 4)."""
    steps = _normalise(step_features(points))
    if len(steps) >= window:
        return steps[-window:]
    pad = np.zeros((window - len(steps), FEATURE_DIM), dtype=np.float32)
    return np.vstack([pad, steps]) if len(steps) else pad


def iter_windows(points: list[tuple[float, float, float]], window: int = WINDOW):
    """Yield all sliding windows over a trajectory (for training)."""
    steps = _normalise(step_features(points))
    if len(steps) < window:
        if len(steps) >= 2:  # short trajectory: one left-padded window
            pad = np.zeros((window - len(steps), FEATURE_DIM), dtype=np.float32)
            yield np.vstack([pad, steps])
        return
    for end in range(window, len(steps) + 1):
        yield steps[end - window : end]
