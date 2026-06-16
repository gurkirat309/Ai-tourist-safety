"""Inactivity / signal drop-off detection.

Flags when too long has elapsed since a tourist's last ping. Thresholds tighten
in higher-risk zones (a 15-min gap in a forest fringe is more alarming than in a
city centre). Pure and deterministic.
"""

from __future__ import annotations

from app.db.enums import IncidentType, RiskCategory
from app.detection.thresholds import (
    INACTIVITY_BASE_CRITICAL_S,
    INACTIVITY_BASE_WARN_S,
    inactivity_factor,
)
from app.detection.types import DetectionSignal, Severity

SOURCE = "detection.inactivity"


def check_inactivity(
    seconds_since_last_ping: float,
    zone_risk: RiskCategory | None = None,
) -> DetectionSignal | None:
    """Flag inactivity given elapsed seconds and the current zone's risk.

    Returns the highest-severity signal, or None if within tolerance.
    """
    factor = inactivity_factor(zone_risk)
    warn_s = INACTIVITY_BASE_WARN_S * factor
    critical_s = INACTIVITY_BASE_CRITICAL_S * factor

    if seconds_since_last_ping >= critical_s:
        severity = Severity.CRITICAL
    elif seconds_since_last_ping >= warn_s:
        severity = Severity.WARNING
    else:
        return None

    minutes = seconds_since_last_ping / 60.0
    over = (seconds_since_last_ping - warn_s) / warn_s if warn_s else 0.0
    confidence = min(1.0, 0.6 + 0.4 * over)
    return DetectionSignal(
        type=IncidentType.INACTIVITY,
        severity=severity,
        reason=f"No ping for {minutes:.1f} min",
        confidence=confidence,
        details={
            "seconds_since_last_ping": round(seconds_since_last_ping, 1),
            "zone_risk": zone_risk.value if zone_risk else None,
            "warn_threshold_s": round(warn_s, 1),
            "critical_threshold_s": round(critical_s, 1),
        },
        source=SOURCE,
    )
