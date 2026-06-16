"""Demo: triage an incident built from seeded Bengaluru data.

Picks a seeded tourist on the Bannerghatta (restricted) trek, fabricates a
geofence-breach incident at their last position, runs the Incident Triage agent
(dry-run heuristic), and prints the structured advisory result + the Alert it
would create. Nothing is committed (rolled back at the end).

Run:  uv run python -m scripts.demo_triage   (needs infra up + seed loaded)
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.agents.triage import IncidentTriageAgent, to_alert
from app.db.enums import IncidentType
from app.db.models import Incident, LocationPing, Tourist
from app.db.session import SessionLocal
from app.detection.types import DetectionSignal, Severity
from app.services.llm import LLMClient


def main() -> None:
    db = SessionLocal()
    try:
        tourist = db.execute(
            select(Tourist).where(Tourist.display_name == "Kenji Tanaka")
        ).scalars().first()
        if tourist is None:
            print("Seed data not found — run `make seed` first.")
            return

        last = db.execute(
            select(LocationPing)
            .where(LocationPing.tourist_id == tourist.id)
            .order_by(LocationPing.recorded_at.desc())
        ).scalars().first()

        # Fabricate a geofence-breach incident with a critical signal attached.
        signal = DetectionSignal(
            type=IncidentType.GEOFENCE_BREACH,
            severity=Severity.CRITICAL,
            reason="Entered restricted zone 'Bannerghatta Forest Fringe'",
            confidence=1.0,
            source="detection.geofence",
        )
        incident = Incident(
            tourist_id=tourist.id,
            incident_type=IncidentType.GEOFENCE_BREACH,
            geom=last.geom,
            detected_at=datetime.now(UTC),
            details={"signals": [signal.as_dict()]},
        )
        db.add(incident)
        db.flush()  # assign id, no commit

        agent = IncidentTriageAgent(db, llm=LLMClient(dry_run=True))
        result = agent.triage(incident)

        print(f"=== Triage for incident {incident.id} ({tourist.display_name}) ===")
        print(f"escalation : {result.escalation.value.upper()}")
        print(f"summary    : {result.summary}")
        print(f"rationale  : {result.rationale}")
        print("actions    :")
        for a in result.recommended_actions:
            print(f"   - {a}")

        alert = to_alert(result, incident)
        print(f"\n-> would create Alert (severity={alert.severity.value}, "
              f"by={alert.created_by})")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
