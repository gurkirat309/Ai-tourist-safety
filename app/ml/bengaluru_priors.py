"""Bengaluru geography, NCRB-derived zone priors, and temporal risk patterns.

India has no public point-level (lat/lon + timestamp) crime dataset, so per the
project decision we use **real published aggregates as zone-level priors** and
generate synthetic incidents conditioned on them (see `app.ml.dataset`).

The numeric priors below are *approximate relative intensities* informed by:
  * NCRB "Crime in India" — metropolitan-city tables (Bengaluru), and
  * data.gov.in / Bengaluru City Police published summaries.
They are intentionally easy to tune; adjust `ZONE_PRIORS` / the multipliers as
better figures become available. They encode *relative* risk, not absolute
crime counts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# --- Bengaluru bounding box (WGS84) ---------------------------------------
LON_MIN, LON_MAX = 77.45, 77.75
LAT_MIN, LAT_MAX = 12.80, 13.10

# Grid cell size in degrees (~1.1 km). Used for spatial bucketing / counts.
CELL_DEG = 0.01

# Background relative intensity for areas not covered by a named prior zone.
BACKGROUND_INTENSITY = 0.15


@dataclass(frozen=True)
class ZonePrior:
    name: str
    center_lon: float
    center_lat: float
    radius_deg: float
    # Relative base intensity in [0, 1]; higher = more incident-prone.
    intensity: float


# Centres align with the seeded zones (scripts/seed.py) for consistency.
ZONE_PRIORS: list[ZonePrior] = [
    ZonePrior("Majestic (KSR / Bus Stand)", 77.5720, 12.9770, 0.010, 0.85),
    ZonePrior("MG Road", 77.6090, 12.9750, 0.012, 0.55),
    ZonePrior("Koramangala", 77.6245, 12.9352, 0.014, 0.55),
    ZonePrior("Electronic City", 77.6770, 12.8450, 0.018, 0.40),
    ZonePrior("Bannerghatta Forest Fringe", 77.5770, 12.8000, 0.035, 0.60),
    ZonePrior("Cubbon Park", 77.5950, 12.9760, 0.008, 0.25),
]


def spatial_intensity(lat: float, lon: float) -> float:
    """Relative spatial risk intensity at a point.

    Each prior zone contributes a Gaussian-falloff bump centred on its centroid;
    we take the max over zones and the background floor. Result in [0, 1].
    """
    best = BACKGROUND_INTENSITY
    for z in ZONE_PRIORS:
        d2 = (lon - z.center_lon) ** 2 + (lat - z.center_lat) ** 2
        # Falloff so intensity ~halves near the zone radius.
        falloff = math.exp(-d2 / (2 * (z.radius_deg**2)))
        best = max(best, z.intensity * falloff)
    return min(1.0, best)


# --- Temporal patterns -----------------------------------------------------
# Hour-of-day multiplier (0..23). Risk peaks late night, troughs at dawn.
# Wide dynamic range so the time-of-day effect is clearly learnable.
_HOUR_MULTIPLIER = [
    1.70, 1.50, 1.20, 0.90, 0.60, 0.45,  # 00-05
    0.40, 0.45, 0.55, 0.65, 0.75, 0.85,  # 06-11
    0.90, 0.90, 0.90, 0.95, 1.05, 1.25,  # 12-17
    1.55, 1.85, 2.05, 2.10, 2.00, 1.85,  # 18-23
]

# Day-of-week multiplier (Mon=0 .. Sun=6); weekends notably higher.
_DOW_MULTIPLIER = [0.90, 0.90, 0.95, 1.00, 1.20, 1.40, 1.25]


def hour_multiplier(hour: int) -> float:
    return _HOUR_MULTIPLIER[hour % 24]


def dow_multiplier(dow: int) -> float:
    return _DOW_MULTIPLIER[dow % 7]


def temporal_multiplier(hour: int, dow: int) -> float:
    """Combined time-of-day x day-of-week multiplier."""
    return hour_multiplier(hour) * dow_multiplier(dow)


# --- Grid helpers ----------------------------------------------------------
def cell_index(lat: float, lon: float) -> tuple[int, int]:
    """Integer (row, col) grid cell for a point, clamped to the bbox."""
    col = int((lon - LON_MIN) / CELL_DEG)
    row = int((lat - LAT_MIN) / CELL_DEG)
    n_rows, n_cols = grid_shape()
    row = max(0, min(n_rows - 1, row))
    col = max(0, min(n_cols - 1, col))
    return (row, col)


def cell_center(row: int, col: int) -> tuple[float, float]:
    """(lat, lon) centre of a grid cell."""
    lat = LAT_MIN + (row + 0.5) * CELL_DEG
    lon = LON_MIN + (col + 0.5) * CELL_DEG
    return (lat, lon)


def grid_shape() -> tuple[int, int]:
    """(n_rows, n_cols) of the Bengaluru grid."""
    n_rows = math.ceil((LAT_MAX - LAT_MIN) / CELL_DEG)
    n_cols = math.ceil((LON_MAX - LON_MIN) / CELL_DEG)
    return (n_rows, n_cols)
