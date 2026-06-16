"""Shared types for the deterministic detection layer.

Detectors are fast, rule-based, and **never** call an LLM. Each returns zero or
more `DetectionSignal`s. Confidence here is a deterministic, rule-derived number
(e.g. how far past a threshold), not a model probability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.db.enums import IncidentType


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class DetectionSignal:
    """A single deterministic finding from a detector."""

    type: IncidentType
    severity: Severity
    reason: str
    # Deterministic, rule-derived confidence in [0, 1].
    confidence: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)
    # Constant identifying the producing detector (grounding/traceability).
    source: str = "detection"

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "reason": self.reason,
            "confidence": round(self.confidence, 3),
            "details": self.details,
            "source": self.source,
        }
