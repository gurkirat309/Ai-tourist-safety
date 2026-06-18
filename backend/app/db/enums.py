"""Shared enumerations used across models and schemas.

Using str-based enums so values are human-readable in the DB and JSON.
"""

from enum import StrEnum


class UserRole(StrEnum):
    """Authentication role — drives what a logged-in user can see/do."""

    TOURIST = "tourist"
    POLICE = "police"


class ConsentPurpose(StrEnum):
    """DPDP purpose for which a tourist's location is processed."""

    SAFETY_MONITORING = "safety_monitoring"
    EMERGENCY_RESPONSE = "emergency_response"
    ANALYTICS = "analytics"


class RiskCategory(StrEnum):
    """Coarse risk classification for a zone."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    RESTRICTED = "restricted"


class RiskEventType(StrEnum):
    """Type of an externally-sourced or detected risk event."""

    CRIME = "crime"
    NATURAL_HAZARD = "natural_hazard"
    CIVIL_UNREST = "civil_unrest"
    ACCIDENT = "accident"
    HEALTH = "health"
    ADVISORY = "advisory"
    OTHER = "other"


class IncidentType(StrEnum):
    """Type of a detected/flagged incident (from the detection layer)."""

    GEOFENCE_BREACH = "geofence_breach"
    ROUTE_DEVIATION = "route_deviation"
    INACTIVITY = "inactivity"
    CROWD_DENSITY = "crowd_density"
    PANIC = "panic"
    OTHER = "other"


class IncidentStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AlertSeverity(StrEnum):
    """Escalation level for an alert (advisory output for humans)."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    CLOSED = "closed"
