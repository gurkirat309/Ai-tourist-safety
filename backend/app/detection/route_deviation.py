"""Route deviation: how far a position is from the planned route, plus a speed
sanity check between consecutive pings.

Pure and deterministic. Distances in meters (geodesic).
"""

from __future__ import annotations

from app.db.enums import IncidentType
from app.detection.geo import distance_m, distance_point_to_route_m
from app.detection.thresholds import (
    IMPLAUSIBLE_SPEED_MPS,
    ROUTE_DEVIATION_CRITICAL_M,
    ROUTE_DEVIATION_WARN_M,
)
from app.detection.types import DetectionSignal, Severity

SOURCE = "detection.route_deviation"


def check_route_deviation(
    lat: float,
    lon: float,
    route: list[tuple[float, float]],
) -> DetectionSignal | None:
    """Flag if the point is significantly off the planned route.

    `route` is a list of (lon, lat) pairs. Returns the highest-severity signal,
    or None if within tolerance.
    """
    if not route:
        return None

    dist = distance_point_to_route_m(lat, lon, route)
    if dist >= ROUTE_DEVIATION_CRITICAL_M:
        severity = Severity.CRITICAL
    elif dist >= ROUTE_DEVIATION_WARN_M:
        severity = Severity.WARNING
    else:
        return None

    # Confidence scales with how far past the warn threshold we are (capped).
    over = (dist - ROUTE_DEVIATION_WARN_M) / ROUTE_DEVIATION_WARN_M
    confidence = min(1.0, 0.6 + 0.4 * over)
    return DetectionSignal(
        type=IncidentType.ROUTE_DEVIATION,
        severity=severity,
        reason=f"{dist:.0f} m off planned route",
        confidence=confidence,
        details={"deviation_m": round(dist, 1)},
        source=SOURCE,
    )


def check_speed_anomaly(
    prev_lat: float,
    prev_lon: float,
    prev_ts_s: float,
    lat: float,
    lon: float,
    ts_s: float,
) -> DetectionSignal | None:
    """Flag an implausible implied speed between two consecutive pings."""
    dt = ts_s - prev_ts_s
    if dt <= 0:
        return None
    dist = distance_m(prev_lat, prev_lon, lat, lon)
    speed = dist / dt
    if speed < IMPLAUSIBLE_SPEED_MPS:
        return None
    return DetectionSignal(
        type=IncidentType.ROUTE_DEVIATION,
        severity=Severity.WARNING,
        reason=f"Implausible speed {speed:.0f} m/s between pings",
        confidence=0.7,
        details={"speed_mps": round(speed, 1), "dt_s": round(dt, 1)},
        source=SOURCE,
    )
