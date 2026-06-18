"""Seed the database with synthetic Bengaluru data.

Creates zones (commercial centre, busy neighbourhoods, a transit hub, a city
park, an IT corridor, and a forest fringe), tourists with consent + planned
routes, and location trajectories covering normal / deviating / going-silent
scenarios.

Run:  uv run python -m scripts.seed   (or: make seed)
Idempotent: clears the domain tables first.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.enums import ConsentPurpose, RiskCategory, RiskEventType, UserRole
from app.db.models import (
    Alert,
    Incident,
    LocationPing,
    RiskEvent,
    Tourist,
    User,
    Zone,
)
from app.db.session import SessionLocal
from app.db.spatial import (
    linestring_to_geom,
    point_to_geom,
    polygon_to_geom,
)
from app.services.security import hash_password
from scripts.synthetic import Scenario, generate_trajectory

log = get_logger(__name__)


def _rect(clon: float, clat: float, half: float) -> list[tuple[float, float]]:
    """Axis-aligned rectangle (closed ring) around a centre, half-size in deg."""
    return [
        (clon - half, clat - half),
        (clon + half, clat - half),
        (clon + half, clat + half),
        (clon - half, clat + half),
        (clon - half, clat - half),
    ]


# (name, description, center_lon, center_lat, half_deg, risk, restricted, capacity)
ZONES = [
    ("MG Road", "Central commercial / shopping district", 77.6090, 12.9750, 0.008,
     RiskCategory.MODERATE, False, 6000),
    ("Koramangala", "Busy nightlife & dining neighbourhood", 77.6245, 12.9352, 0.010,
     RiskCategory.MODERATE, False, 5000),
    ("Majestic (KSR / Bus Stand)", "Major transit hub, pickpocketing hotspot",
     77.5720, 12.9770, 0.005, RiskCategory.HIGH, False, 8000),
    ("Cubbon Park", "Large city park, low risk", 77.5950, 12.9760, 0.006,
     RiskCategory.LOW, False, 3000),
    ("Electronic City", "IT corridor on the southern outskirts", 77.6770, 12.8450,
     0.014, RiskCategory.MODERATE, False, None),
    ("Bannerghatta Forest Fringe", "Forest/park edge, wildlife, poor signal",
     77.5770, 12.8000, 0.030, RiskCategory.HIGH, True, None),
]


def seed() -> None:
    db = SessionLocal()
    try:
        # --- clear domain tables (children first) ---
        # Drop tourist-linked user accounts too (keep police accounts).
        db.execute(delete(User).where(User.role == UserRole.TOURIST))
        for model in (Alert, Incident, RiskEvent, LocationPing, Tourist, Zone):
            db.execute(delete(model))
        db.commit()
        log.info("Cleared existing domain rows")

        # --- police demo account (idempotent) ---
        settings = get_settings()
        police_email = settings.police_demo_email.lower()
        existing = db.execute(
            select(User).where(User.email == police_email)
        ).scalars().first()
        if existing is None:
            db.add(User(
                email=police_email,
                hashed_password=hash_password(settings.police_demo_password),
                role=UserRole.POLICE,
            ))
            db.commit()
            log.info("Created police demo account: %s", police_email)
        else:
            log.info("Police demo account already exists: %s", police_email)

        # --- zones ---
        zones: dict[str, Zone] = {}
        for name, desc, clon, clat, half, risk, restricted, cap in ZONES:
            z = Zone(
                name=name,
                description=desc,
                risk_category=risk,
                restricted=restricted,
                capacity=cap,
                geom=polygon_to_geom(_rect(clon, clat, half)),
            )
            db.add(z)
            zones[name] = z
        db.commit()
        log.info("Inserted %d zones", len(zones))

        # --- a couple of grounded risk events (geo-tagged, with confidence) ---
        now = datetime.now(UTC)
        db.add_all([
            RiskEvent(
                event_type=RiskEventType.CRIME,
                title="Pickpocketing reports at Majestic bus stand",
                description="Multiple theft complaints near KSR / Kempegowda hub.",
                geom=point_to_geom(12.9770, 77.5720),
                zone_id=zones["Majestic (KSR / Bus Stand)"].id,
                source="seed:synthetic",
                event_time=now - timedelta(hours=3),
                confidence=0.8,
            ),
            RiskEvent(
                event_type=RiskEventType.NATURAL_HAZARD,
                title="Wildlife movement near Bannerghatta fringe",
                description="Animal sightings reported; limited mobile coverage.",
                geom=point_to_geom(12.8000, 77.5770),
                zone_id=zones["Bannerghatta Forest Fringe"].id,
                source="seed:synthetic",
                event_time=now - timedelta(hours=8),
                confidence=0.6,
            ),
        ])
        db.commit()
        log.info("Inserted 2 risk events")

        # --- tourists + trajectories ---
        # Route 1: MG Road -> Cubbon Park, a central urban walk (moderate->low).
        route_city = [
            (77.6090, 12.9750),
            (77.6030, 12.9755),
            (77.5980, 12.9758),
            (77.5950, 12.9760),
        ]
        # Route 2: Bannerghatta forest-fringe trail (restricted/high).
        route_trek = [
            (77.5750, 12.7980),
            (77.5780, 12.8010),
            (77.5810, 12.8040),
            (77.5840, 12.8070),
        ]

        plan = [
            ("Aarav Sharma", "IN", route_city, Scenario.NORMAL, 101),
            ("Mia Wilson", "GB", route_city, Scenario.DEVIATING, 202),
            ("Kenji Tanaka", "JP", route_trek, Scenario.GOING_SILENT, 303),
            ("Lucas Müller", "DE", route_trek, Scenario.NORMAL, 404),
        ]

        start = now - timedelta(hours=1)
        for name, nat, route, scenario, seed_val in plan:
            t = Tourist(
                display_name=name,
                nationality=nat,
                emergency_contact="+91-0000000000",
                planned_route=linestring_to_geom(route),
                consent_given=True,
                consent_timestamp=now,
                consent_purpose=ConsentPurpose.SAFETY_MONITORING,
                retention_until=now + timedelta(days=30),
                is_active=True,
            )
            db.add(t)
            db.flush()  # assign t.id

            pings = generate_trajectory(
                route,
                scenario=scenario,
                n_points=30,
                start_time=start,
                interval_s=60,
                seed=seed_val,
            )
            for p in pings:
                db.add(
                    LocationPing(
                        tourist_id=t.id,
                        geom=point_to_geom(p.lat, p.lon),
                        recorded_at=p.recorded_at,
                        speed_mps=p.speed_mps,
                        source="seed",
                    )
                )
            log.info("Tourist %-14s scenario=%-12s pings=%d", name, scenario, len(pings))

        db.commit()
        log.info("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
