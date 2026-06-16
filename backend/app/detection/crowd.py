"""Crowd density detection.

Two modes:
  * zone-based   — count of recent pings vs a zone's `capacity` (preferred when
                   a zone with capacity is known).
  * geohash-based— aggregate pings into geohash cells to find hotspots where no
                   capacity-bearing zone exists.

Pure, deterministic aggregation — no DB, no LLM.
"""

from __future__ import annotations

from collections import Counter

from app.db.enums import IncidentType
from app.detection.thresholds import (
    CROWD_CRITICAL_FRACTION,
    CROWD_WARN_FRACTION,
)
from app.detection.types import DetectionSignal, Severity

SOURCE = "detection.crowd"

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def geohash_encode(lat: float, lon: float, precision: int = 7) -> str:
    """Encode a lat/lon to a geohash string (standard base32 algorithm)."""
    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    bits = [16, 8, 4, 2, 1]
    out: list[str] = []
    bit = 0
    ch = 0
    even = True
    while len(out) < precision:
        if even:
            mid = sum(lon_interval) / 2
            if lon > mid:
                ch |= bits[bit]
                lon_interval[0] = mid
            else:
                lon_interval[1] = mid
        else:
            mid = sum(lat_interval) / 2
            if lat > mid:
                ch |= bits[bit]
                lat_interval[0] = mid
            else:
                lat_interval[1] = mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            out.append(_BASE32[ch])
            bit = 0
            ch = 0
    return "".join(out)


def aggregate_by_geohash(
    points: list[tuple[float, float]], precision: int = 7
) -> dict[str, int]:
    """Count points per geohash cell. `points` are (lat, lon)."""
    return dict(Counter(geohash_encode(lat, lon, precision) for lat, lon in points))


def check_zone_crowd(
    current_count: int,
    capacity: int | None,
    *,
    zone_name: str | None = None,
) -> DetectionSignal | None:
    """Flag congestion when occupancy nears/exceeds a zone's capacity."""
    if not capacity or capacity <= 0:
        return None

    fraction = current_count / capacity
    if fraction >= CROWD_CRITICAL_FRACTION:
        severity = Severity.CRITICAL
    elif fraction >= CROWD_WARN_FRACTION:
        severity = Severity.WARNING
    else:
        return None

    return DetectionSignal(
        type=IncidentType.CROWD_DENSITY,
        severity=severity,
        reason=(
            f"Crowd at {fraction * 100:.0f}% of capacity"
            + (f" in '{zone_name}'" if zone_name else "")
        ),
        confidence=min(1.0, fraction),
        details={
            "current_count": current_count,
            "capacity": capacity,
            "fraction": round(fraction, 3),
            "zone": zone_name,
        },
        source=SOURCE,
    )
