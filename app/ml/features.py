"""Feature engineering for the area-risk model.

This is the single source of truth for turning a (location, time) into a model
feature row, so training and inference cannot drift apart.

Features (kept deliberately small / tabular):
  * hour            — hour of day (0..23)
  * dow             — day of week (Mon=0 .. Sun=6)
  * is_weekend      — 1 if Sat/Sun
  * is_night        — 1 if 20:00..05:59
  * lat, lon        — coordinates (let the GBM learn fine spatial structure)
  * zone_prior      — NCRB-derived zone risk prior at this point (the realistic
                      "we know this area's historical risk" signal the brief
                      calls for; combined with time + recent counts)
  * recent_incidents— incidents in the same cell over the trailing window
"""

from __future__ import annotations

from datetime import datetime

from app.ml.bengaluru_priors import spatial_intensity

# Ordered feature names — the column order the model is trained/served with.
FEATURE_NAMES: list[str] = [
    "hour",
    "dow",
    "is_weekend",
    "is_night",
    "lat",
    "lon",
    "zone_prior",
    "recent_incidents",
]

NIGHT_START = 20  # 20:00
NIGHT_END = 6  # 06:00 (exclusive)


def is_night_hour(hour: int) -> bool:
    return hour >= NIGHT_START or hour < NIGHT_END


def build_features(
    lat: float,
    lon: float,
    when: datetime,
    recent_incidents: float = 0.0,
) -> dict[str, float]:
    """Build a single feature dict from raw inputs."""
    hour = when.hour
    dow = when.weekday()
    return {
        "hour": float(hour),
        "dow": float(dow),
        "is_weekend": 1.0 if dow >= 5 else 0.0,
        "is_night": 1.0 if is_night_hour(hour) else 0.0,
        "lat": float(lat),
        "lon": float(lon),
        "zone_prior": float(spatial_intensity(lat, lon)),
        "recent_incidents": float(recent_incidents),
    }


def features_to_row(feats: dict[str, float]) -> list[float]:
    """Order a feature dict into the canonical row vector."""
    return [feats[name] for name in FEATURE_NAMES]
