"""Centralized, tunable thresholds for the detection layer.

Kept in one place so behavior is easy to audit and adjust. Inactivity tightens
in higher-risk zones via `RISK_INACTIVITY_FACTOR`.
"""

from __future__ import annotations

from app.db.enums import RiskCategory

# --- Route deviation (meters from planned route) ---
ROUTE_DEVIATION_WARN_M = 75.0
ROUTE_DEVIATION_CRITICAL_M = 150.0
# Implausible speed between consecutive pings (m/s); ~30 m/s = 108 km/h on foot.
IMPLAUSIBLE_SPEED_MPS = 30.0

# --- Inactivity / drop-off (seconds since last ping) ---
INACTIVITY_BASE_WARN_S = 15 * 60  # 15 min
INACTIVITY_BASE_CRITICAL_S = 30 * 60  # 30 min
# Multiplier applied to the base thresholds per zone risk; lower = stricter.
RISK_INACTIVITY_FACTOR: dict[RiskCategory, float] = {
    RiskCategory.LOW: 1.0,
    RiskCategory.MODERATE: 0.75,
    RiskCategory.HIGH: 0.5,
    RiskCategory.RESTRICTED: 0.5,
}

# --- Crowd density (fraction of zone capacity) ---
CROWD_WARN_FRACTION = 0.75
CROWD_CRITICAL_FRACTION = 0.90
# Default window over which "current" pings are counted (seconds).
CROWD_WINDOW_S = 10 * 60  # 10 min


def inactivity_factor(risk: RiskCategory | None) -> float:
    """Threshold multiplier for a zone's risk category (default 1.0)."""
    if risk is None:
        return 1.0
    return RISK_INACTIVITY_FACTOR.get(risk, 1.0)
