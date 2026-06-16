"""Tests for the synthetic trajectory generator (no DB required)."""

import math
from datetime import UTC, datetime

from scripts.synthetic import Scenario, generate_trajectory

ROUTE = [
    (73.7560, 15.5410),
    (73.7545, 15.5470),
    (73.7525, 15.5520),
    (73.7510, 15.5560),
]
START = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)


def test_normal_emits_all_points():
    pings = generate_trajectory(
        ROUTE, scenario=Scenario.NORMAL, n_points=30, start_time=START, seed=1
    )
    assert len(pings) == 30
    # Timestamps strictly increasing.
    times = [p.recorded_at for p in pings]
    assert times == sorted(times)


def test_going_silent_truncates():
    pings = generate_trajectory(
        ROUTE, scenario=Scenario.GOING_SILENT, n_points=30, start_time=START, seed=1
    )
    # Only ~40% of points are emitted.
    assert len(pings) == 12


def test_deviating_drifts_further_than_normal():
    end = ROUTE[-1]

    normal = generate_trajectory(
        ROUTE, scenario=Scenario.NORMAL, n_points=30, start_time=START, seed=7
    )
    deviating = generate_trajectory(
        ROUTE, scenario=Scenario.DEVIATING, n_points=30, start_time=START, seed=7
    )

    def dist_to_end(p):
        return math.dist((p.lon, p.lat), end)

    # The deviating trajectory's final point should be much farther from the
    # planned endpoint than the normal one's.
    assert dist_to_end(deviating[-1]) > dist_to_end(normal[-1]) * 3
