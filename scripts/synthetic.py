"""Synthetic trajectory generation (Bengaluru-anchored).

Pure, deterministic-with-seed helpers that turn a planned route into a stream of
location pings under three scenarios:

  * NORMAL       — follows the route with small GPS jitter.
  * DEVIATING    — progressively drifts away from the route.
  * GOING_SILENT — follows the route, then stops reporting partway through.

These doubles as fixtures for the M2 detection layer. Coordinates are (lon, lat)
to match GeoJSON / Shapely order; pings carry (lat, lon, recorded_at, speed_mps).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

# Rough meters-per-degree at Bengaluru's latitude (~12.97 N). Good enough for
# synthetic jitter/offsets; the real distance math in M2 uses geodesic functions.
_M_PER_DEG_LAT = 110_574.0
_M_PER_DEG_LON = 108_500.0  # cos(12.97 deg) * 111_320


class Scenario(StrEnum):
    NORMAL = "normal"
    DEVIATING = "deviating"
    GOING_SILENT = "going_silent"


@dataclass
class SynthPing:
    lat: float
    lon: float
    recorded_at: datetime
    speed_mps: float


def _interpolate(route: list[tuple[float, float]], frac: float) -> tuple[float, float]:
    """Point at fractional distance `frac` (0..1) along a polyline of (lon, lat)."""
    if frac <= 0:
        return route[0]
    if frac >= 1:
        return route[-1]

    seg_lengths = [
        math.dist(route[i], route[i + 1]) for i in range(len(route) - 1)
    ]
    total = sum(seg_lengths)
    target = frac * total

    acc = 0.0
    for i, seg in enumerate(seg_lengths):
        if acc + seg >= target:
            t = (target - acc) / seg if seg else 0.0
            lon = route[i][0] + t * (route[i + 1][0] - route[i][0])
            lat = route[i][1] + t * (route[i + 1][1] - route[i][1])
            return (lon, lat)
        acc += seg
    return route[-1]


def _offset_meters(lon: float, lat: float, east_m: float, north_m: float) -> tuple[float, float]:
    return (
        lon + east_m / _M_PER_DEG_LON,
        lat + north_m / _M_PER_DEG_LAT,
    )


def generate_trajectory(
    route: list[tuple[float, float]],
    *,
    scenario: Scenario = Scenario.NORMAL,
    n_points: int = 30,
    start_time: datetime,
    interval_s: int = 60,
    jitter_m: float = 8.0,
    seed: int | None = None,
) -> list[SynthPing]:
    """Generate a list of pings along `route` for the given scenario."""
    rng = random.Random(seed)
    pings: list[SynthPing] = []

    # GOING_SILENT: only emit the first ~40% of points, then silence.
    emit_count = n_points
    if scenario is Scenario.GOING_SILENT:
        emit_count = max(2, int(n_points * 0.4))

    for i in range(emit_count):
        frac = i / (n_points - 1) if n_points > 1 else 0.0
        lon, lat = _interpolate(route, frac)

        # Base GPS jitter.
        east = rng.gauss(0, jitter_m)
        north = rng.gauss(0, jitter_m)

        # DEVIATING: add a growing perpendicular drift (up to ~400 m).
        if scenario is Scenario.DEVIATING:
            drift = 400.0 * frac
            east += drift
            north += drift * 0.3

        lon, lat = _offset_meters(lon, lat, east, north)
        ts = start_time + timedelta(seconds=i * interval_s)
        speed = max(0.0, rng.gauss(1.4, 0.4))  # ~walking pace m/s
        pings.append(SynthPing(lat=lat, lon=lon, recorded_at=ts, speed_mps=speed))

    return pings
