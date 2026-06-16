"""M2 tests for the deterministic detection layer (pure, no DB / no LLM)."""

from datetime import UTC, datetime

from app.db.enums import RiskCategory
from app.detection.crowd import (
    aggregate_by_geohash,
    check_zone_crowd,
    geohash_encode,
)
from app.detection.geofence import ZoneInfo, check_geofence
from app.detection.inactivity import check_inactivity
from app.detection.route_deviation import (
    check_route_deviation,
    check_speed_anomaly,
)
from app.detection.types import Severity
from scripts.synthetic import Scenario, generate_trajectory

# A square zone around (lon=77.572, lat=12.977) — "Majestic"-ish.
RING = [
    (77.567, 12.972),
    (77.577, 12.972),
    (77.577, 12.982),
    (77.567, 12.982),
    (77.567, 12.972),
]
ROUTE = [
    (77.6090, 12.9750),
    (77.6030, 12.9755),
    (77.5980, 12.9758),
    (77.5950, 12.9760),
]


# --- Geofencing ---
def test_geofence_restricted_is_critical():
    zones = [ZoneInfo("Forbidden", RING, RiskCategory.HIGH, restricted=True)]
    signals = check_geofence(12.977, 77.572, zones)
    assert len(signals) == 1
    assert signals[0].severity is Severity.CRITICAL


def test_geofence_high_risk_is_warning():
    zones = [ZoneInfo("Risky", RING, RiskCategory.HIGH, restricted=False)]
    signals = check_geofence(12.977, 77.572, zones)
    assert signals[0].severity is Severity.WARNING


def test_geofence_outside_is_clear():
    zones = [ZoneInfo("Risky", RING, RiskCategory.HIGH, restricted=True)]
    assert check_geofence(13.05, 77.70, zones) == []


# --- Route deviation ---
def test_on_route_no_signal():
    assert check_route_deviation(12.9758, 77.5980, ROUTE) is None


def test_far_off_route_is_critical():
    # ~2 km north of the route.
    sig = check_route_deviation(12.9950, 77.5980, ROUTE)
    assert sig is not None
    assert sig.severity is Severity.CRITICAL
    assert sig.details["deviation_m"] > 150


def test_deviating_trajectory_flags_at_end():
    start = datetime(2026, 6, 16, 10, tzinfo=UTC)
    pings = generate_trajectory(ROUTE, scenario=Scenario.DEVIATING,
                                n_points=30, start_time=start, seed=7)
    last = pings[-1]
    assert check_route_deviation(last.lat, last.lon, ROUTE) is not None


def test_normal_trajectory_stays_on_route():
    start = datetime(2026, 6, 16, 10, tzinfo=UTC)
    pings = generate_trajectory(ROUTE, scenario=Scenario.NORMAL,
                                n_points=30, start_time=start, seed=7)
    # Normal jitter (~8 m) should not trip the 75 m warn threshold.
    flagged = [p for p in pings if check_route_deviation(p.lat, p.lon, ROUTE)]
    assert flagged == []


def test_speed_anomaly():
    # ~1 km in 10 s = 100 m/s -> implausible.
    sig = check_speed_anomaly(12.970, 77.572, 0.0, 12.979, 77.572, 10.0)
    assert sig is not None
    assert sig.details["speed_mps"] > 30


# --- Inactivity (zone-risk-adjusted) ---
def test_inactivity_below_threshold_clear():
    assert check_inactivity(5 * 60, RiskCategory.LOW) is None


def test_inactivity_high_zone_is_stricter():
    # 10 min: fine in LOW (warn at 15 min) but a warning in HIGH (warn at 7.5).
    assert check_inactivity(10 * 60, RiskCategory.LOW) is None
    sig = check_inactivity(10 * 60, RiskCategory.HIGH)
    assert sig is not None
    assert sig.severity is Severity.WARNING


def test_inactivity_critical():
    sig = check_inactivity(40 * 60, RiskCategory.LOW)
    assert sig is not None
    assert sig.severity is Severity.CRITICAL


# --- Crowd density ---
def test_crowd_below_capacity_clear():
    assert check_zone_crowd(100, 1000, zone_name="Park") is None


def test_crowd_over_capacity_critical():
    sig = check_zone_crowd(950, 1000, zone_name="Market")
    assert sig is not None
    assert sig.severity is Severity.CRITICAL


def test_crowd_no_capacity_returns_none():
    assert check_zone_crowd(5000, None) is None


def test_geohash_encode_known_value():
    # Canonical example.
    assert geohash_encode(57.64911, 10.40744, 11) == "u4pruydqqvj"


def test_geohash_aggregation_groups_nearby_points():
    pts = [(12.9770, 77.5720), (12.97701, 77.57201), (13.05, 77.70)]
    agg = aggregate_by_geohash(pts, precision=6)
    # First two collapse to one cell; the far one is separate.
    assert max(agg.values()) == 2
    assert len(agg) == 2
