"""Demo: drive the orchestrator with a live-like trajectory + a panic event.

Creates a temporary tourist on a Bannerghatta (restricted) route, streams a
deviating trajectory through `process_location_update`, then fires the panic
path. Prints the decision trace, then the incidents/alerts created. Cleans up
its own data at the end.

Run:  uv run python -m scripts.demo_orchestrator   (needs infra up + seed + model)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.db.enums import ConsentPurpose
from app.db.models import Alert, Incident, LocationPing, Tourist
from app.db.session import SessionLocal
from app.db.spatial import linestring_to_geom
from app.orchestrator.orchestrator import SafetyOrchestrator
from app.services.llm import LLMClient
from scripts.synthetic import Scenario, generate_trajectory

ROUTE = [
    (77.5750, 12.7980),
    (77.5780, 12.8010),
    (77.5810, 12.8040),
    (77.5840, 12.8070),
]


def main() -> None:
    db = SessionLocal()
    tourist_id = None
    try:
        t = Tourist(
            display_name="Orchestrator Demo",
            consent_given=True,
            consent_timestamp=datetime.now(UTC),
            consent_purpose=ConsentPurpose.SAFETY_MONITORING,
            planned_route=linestring_to_geom(ROUTE),
        )
        db.add(t)
        db.commit()
        tourist_id = t.id

        orch = SafetyOrchestrator(db, llm=LLMClient(dry_run=True))

        start = datetime.now(UTC) - timedelta(minutes=30)
        pings = generate_trajectory(
            ROUTE, scenario=Scenario.DEVIATING, n_points=10,
            start_time=start, interval_s=120, seed=99,
        )

        print("=== Streaming location updates ===")
        for i, p in enumerate(pings):
            res = orch.process_location_update(
                tourist_id, p.lat, p.lon, p.recorded_at, speed_mps=p.speed_mps
            )
            tag = "INCIDENT" if res.incident_created else ("reuse" if res.incident_id else "-")
            risk = None if res.area_risk_score is None else round(res.area_risk_score, 2)
            esc = f"esc={res.escalation}" if res.escalation else ""
            print(f"  ping {i:2d} zone={res.zone_name or '-':28s} risk={risk} "
                  f"sev={[s.severity.value for s in res.signals]} -> {tag} {esc}")

        print("\n=== Panic button ===")
        panic = orch.trigger_panic(tourist_id, 12.8070, 77.5840)
        for line in panic.trace:
            print(f"  {line}")

        # Summary of what landed in the DB.
        incidents = db.execute(
            select(Incident).where(Incident.tourist_id == tourist_id)
        ).scalars().all()
        print(f"\n=== Result: {len(incidents)} incident(s) ===")
        for inc in incidents:
            alerts = db.execute(
                select(Alert).where(Alert.incident_id == inc.id)
            ).scalars().all()
            for a in alerts:
                print(f"  {inc.incident_type.value:16s} -> alert {a.severity.value.upper()} "
                      f": {a.summary[:80]}")
    finally:
        # cleanup (children first)
        if tourist_id is not None:
            inc_ids = db.execute(
                select(Incident.id).where(Incident.tourist_id == tourist_id)
            ).scalars().all()
            if inc_ids:
                db.execute(delete(Alert).where(Alert.incident_id.in_(inc_ids)))
                db.execute(delete(Incident).where(Incident.id.in_(inc_ids)))
            db.execute(delete(LocationPing).where(LocationPing.tourist_id == tourist_id))
            db.execute(delete(Tourist).where(Tourist.id == tourist_id))
            db.commit()
        db.close()


if __name__ == "__main__":
    main()
