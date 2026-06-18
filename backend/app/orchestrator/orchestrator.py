"""Safety orchestrator (M6).

The explicit, debuggable controller that ties the system together. On each
location update it:

  1. persists the ping,
  2. runs the deterministic detection layer (M2) — no LLM here,
  3. consults area risk (M3) and zone risk,
  4. applies escalation thresholds,
  5. creates/dedupes an Incident, then invokes the Triage agent (M5) to attach
     an advisory Alert,
  6. records a decision trace for full traceability.

The panic-button path bypasses thresholds for an immediate CRITICAL escalation.
Control flow is plain Python by design (no agent frameworks). Agents produce
decision support only — nothing here dispatches responders automatically.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.triage import IncidentTriageAgent, to_alert
from app.core.logging import get_logger
from app.db.enums import IncidentStatus, IncidentType
from app.db.models import Alert, Incident, LocationPing, Tourist
from app.db.spatial import geom_to_latlon, point_to_geom
from app.detection.adapters import (
    containing_zone,
    count_recent_pings_in_zone,
    load_zone_infos,
    previous_ping,
    tourist_route,
)
from app.detection.crowd import check_zone_crowd
from app.detection.geofence import check_geofence
from app.detection.inactivity import check_inactivity
from app.detection.route_deviation import check_route_deviation, check_speed_anomaly
from app.detection.thresholds import CROWD_WINDOW_S
from app.detection.types import DetectionSignal, Severity
from app.services.llm import LLMClient

log = get_logger(__name__)

# Minimum signal severity that opens an incident (INFO never does).
_SEV_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.CRITICAL: 2}
INCIDENT_MIN_SEVERITY = Severity.WARNING

# Reuse an existing OPEN incident of the same (tourist, type) instead of
# creating duplicates within this window.
INCIDENT_DEDUP_WINDOW_MIN = 30


@dataclass
class OrchestrationResult:
    ping_id: uuid.UUID | None = None
    signals: list[DetectionSignal] = field(default_factory=list)
    area_risk_score: float | None = None
    zone_name: str | None = None
    incident_id: uuid.UUID | None = None
    incident_created: bool = False
    alert_id: uuid.UUID | None = None
    escalation: str | None = None
    trace: list[str] = field(default_factory=list)

    def log_line(self, msg: str) -> None:
        self.trace.append(msg)
        log.info(msg)


class SafetyOrchestrator:
    def __init__(self, db: Session, *, llm: LLMClient | None = None) -> None:
        self.db = db
        self.llm = llm or LLMClient()

    # --- main entrypoint --------------------------------------------------
    def process_location_update(
        self,
        tourist_id: uuid.UUID,
        lat: float,
        lon: float,
        when: datetime | None = None,
        *,
        speed_mps: float | None = None,
        accuracy_m: float | None = None,
        source: str = "api",
    ) -> OrchestrationResult:
        when = when or datetime.now(UTC)
        result = OrchestrationResult()

        # 1. persist the ping
        prev = previous_ping(self.db, tourist_id, when)
        ping = LocationPing(
            tourist_id=tourist_id,
            geom=point_to_geom(lat, lon),
            recorded_at=when,
            speed_mps=speed_mps,
            accuracy_m=accuracy_m,
            source=source,
        )
        self.db.add(ping)
        self.db.flush()
        result.ping_id = ping.id

        # 2. detection layer (deterministic)
        zones = load_zone_infos(self.db)
        signals: list[DetectionSignal] = list(check_geofence(lat, lon, zones))

        tourist = self.db.get(Tourist, tourist_id)
        route = tourist_route(tourist.planned_route) if tourist else None
        if route:
            dev = check_route_deviation(lat, lon, route)
            if dev:
                signals.append(dev)

        zone = containing_zone(self.db, lat, lon)
        if zone is not None:
            result.zone_name = zone.name

        if prev is not None:
            gap_s = (when - prev.recorded_at).total_seconds()
            inact = check_inactivity(gap_s, zone.risk_category if zone else None)
            if inact:
                signals.append(inact)

            plat, plon = geom_to_latlon(prev.geom)
            spd = check_speed_anomaly(
                plat, plon, prev.recorded_at.timestamp(), lat, lon, when.timestamp()
            )
            if spd:
                signals.append(spd)

        if zone is not None and zone.capacity:
            count = count_recent_pings_in_zone(self.db, zone, CROWD_WINDOW_S, now=when)
            crowd = check_zone_crowd(count, zone.capacity, zone_name=zone.name)
            if crowd:
                signals.append(crowd)

        # Advisory ML: LSTM trajectory-anomaly signal. No-op if torch/model
        # absent; complements (never replaces) the deterministic detectors.
        lstm_sig = self._lstm_signal(tourist_id, when)
        if lstm_sig:
            signals.append(lstm_sig)

        result.signals = signals

        # 3. consult area risk (M3)
        result.area_risk_score = self._area_risk(lat, lon, when)
        result.log_line(
            f"ping@({lat:.4f},{lon:.4f}) zone={result.zone_name} "
            f"signals={[s.severity.value for s in signals]} "
            f"area_risk={result.area_risk_score}"
        )

        # 4. escalation threshold
        top = self._max_severity(signals)
        if top is None or _SEV_RANK[top] < _SEV_RANK[INCIDENT_MIN_SEVERITY]:
            result.log_line("No incident: below escalation threshold")
            self.db.commit()
            return result

        # 5. create/dedupe incident + triage + alert
        incident, created = self._get_or_create_incident(
            tourist_id, lat, lon, when, signals, result.area_risk_score, zone
        )
        result.incident_id = incident.id
        result.incident_created = created

        if created:
            # Triage + alert only for new incidents (avoids alert spam and, in
            # live mode, an LLM call on every ping of an ongoing incident).
            alert = self._triage_and_alert(incident)
            result.alert_id = alert.id
            result.escalation = alert.severity.value
            result.log_line(
                f"Created incident {incident.id} ({incident.incident_type.value}); "
                f"triage escalation={alert.severity.value} alert={alert.id}"
            )
        else:
            existing = self.db.execute(
                select(Alert)
                .where(Alert.incident_id == incident.id)
                .order_by(Alert.created_at.desc())
                .limit(1)
            ).scalars().first()
            if existing is not None:
                result.alert_id = existing.id
                result.escalation = existing.severity.value
            result.log_line(
                f"Reused open incident {incident.id} "
                f"({incident.incident_type.value}); context refreshed, no new alert"
            )

        self.db.commit()
        return result

    # --- panic path -------------------------------------------------------
    def trigger_panic(
        self,
        tourist_id: uuid.UUID,
        lat: float,
        lon: float,
        when: datetime | None = None,
    ) -> OrchestrationResult:
        """Immediate, threshold-bypassing escalation."""
        when = when or datetime.now(UTC)
        result = OrchestrationResult()

        incident = Incident(
            tourist_id=tourist_id,
            zone_id=(z.id if (z := containing_zone(self.db, lat, lon)) else None),
            incident_type=IncidentType.PANIC,
            status=IncidentStatus.OPEN,
            geom=point_to_geom(lat, lon),
            detected_at=when,
            details={"panic": True, "source": "panic_button"},
        )
        self.db.add(incident)
        self.db.flush()
        result.incident_id = incident.id
        result.incident_created = True
        result.log_line(f"PANIC incident {incident.id} created (threshold bypassed)")

        alert = self._triage_and_alert(incident)
        result.alert_id = alert.id
        result.escalation = alert.severity.value
        result.log_line(f"PANIC escalation={alert.severity.value} alert={alert.id}")

        self.db.commit()
        return result

    # --- helpers ----------------------------------------------------------
    def _lstm_signal(self, tourist_id, when) -> DetectionSignal | None:
        """Advisory anomaly signal from the LSTM over the tourist's recent path."""
        try:
            from app.ml.lstm.features import WINDOW
            from app.ml.lstm.infer import score_trajectory
        except Exception:  # noqa: BLE001
            return None
        pings = self.db.execute(
            select(LocationPing)
            .where(LocationPing.tourist_id == tourist_id)
            .order_by(LocationPing.recorded_at.desc())
            .limit(WINDOW + 1)
        ).scalars().all()
        if len(pings) < 3:
            return None
        points = [
            (*geom_to_latlon(p.geom), p.recorded_at.timestamp())
            for p in reversed(pings)
        ]
        prob = score_trajectory(points)
        if prob is None:
            return None
        from app.core.config import get_settings

        if prob < get_settings().lstm_anomaly_threshold:
            return None
        return DetectionSignal(
            type=IncidentType.ROUTE_DEVIATION,
            severity=Severity.WARNING,
            reason=f"Anomalous movement pattern (LSTM p={prob:.2f})",
            confidence=prob,
            details={"anomaly_prob": round(prob, 3)},
            source="ml.trajectory_lstm",
        )

    def _area_risk(self, lat: float, lon: float, when: datetime) -> float | None:
        try:
            from app.ml.risk_model import predict_risk

            return predict_risk(lat, lon, when)
        except Exception as exc:  # noqa: BLE001
            log.info("Area-risk unavailable: %s", exc)
            return None

    @staticmethod
    def _max_severity(signals: list[DetectionSignal]) -> Severity | None:
        if not signals:
            return None
        return max((s.severity for s in signals), key=lambda s: _SEV_RANK[s])

    def _primary_type(self, signals: list[DetectionSignal]) -> IncidentType:
        top = self._max_severity(signals)
        for s in signals:
            if s.severity is top:
                return s.type
        return IncidentType.OTHER

    def _get_or_create_incident(
        self, tourist_id, lat, lon, when, signals, area_risk, zone
    ) -> tuple[Incident, bool]:
        itype = self._primary_type(signals)
        cutoff = when - timedelta(minutes=INCIDENT_DEDUP_WINDOW_MIN)
        existing = self.db.execute(
            select(Incident)
            .where(
                Incident.tourist_id == tourist_id,
                Incident.incident_type == itype,
                Incident.status == IncidentStatus.OPEN,
                Incident.detected_at >= cutoff,
            )
            .order_by(Incident.detected_at.desc())
            .limit(1)
        ).scalars().first()

        details = {
            "signals": [s.as_dict() for s in signals],
            "area_risk_score": area_risk,
        }
        if existing is not None:
            existing.details = details  # refresh latest context
            return existing, False

        incident = Incident(
            tourist_id=tourist_id,
            zone_id=zone.id if zone else None,
            incident_type=itype,
            status=IncidentStatus.OPEN,
            geom=point_to_geom(lat, lon),
            detected_at=when,
            details=details,
        )
        self.db.add(incident)
        self.db.flush()
        return incident, True

    def _triage_and_alert(self, incident: Incident) -> Alert:
        agent = IncidentTriageAgent(self.db, llm=self.llm)
        triage = agent.triage(incident)
        alert = to_alert(triage, incident)
        self.db.add(alert)
        self.db.flush()
        return alert
