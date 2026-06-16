"""Demo: run the deterministic detection layer over the seeded Bengaluru data.

Loads zones, tourists, planned routes, and pings from the DB, then runs all four
detectors (geofence, route deviation, inactivity, crowd) and prints the signals.
Also shows the M3 area-risk score for each tourist's last position, to preview
how the orchestrator (M6) will combine them.

Run:  uv run python -m scripts.demo_detection   (needs infra up + seed loaded)
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import LocationPing, Tourist, Zone
from app.db.session import SessionLocal
from app.db.spatial import geom_to_shape
from app.detection.crowd import aggregate_by_geohash, check_zone_crowd
from app.detection.geofence import ZoneInfo, check_geofence, zones_containing
from app.detection.inactivity import check_inactivity
from app.detection.route_deviation import check_route_deviation


def _zone_infos(db) -> list[ZoneInfo]:
    infos = []
    for z in db.execute(select(Zone)).scalars():
        ring = list(geom_to_shape(z.geom).exterior.coords)  # (lon, lat)
        infos.append(ZoneInfo(z.name, ring, z.risk_category, z.restricted, z.id))
    return infos


def _risk_category_at(lat, lon, zones):
    hits = zones_containing(lat, lon, zones)
    return hits[0].risk_category if hits else None


def main() -> None:
    db = SessionLocal()
    try:
        zones = _zone_infos(db)
        zone_caps = {z.name: z.capacity for z in db.execute(select(Zone)).scalars()}
        print(f"Loaded {len(zones)} zones\n")

        now = datetime.now(UTC)

        # Try to load the risk model (optional).
        predict_risk = None
        try:
            from app.ml.risk_model import predict_risk as _pr

            _pr(12.97, 77.59, now)  # warm/validate
            predict_risk = _pr
        except Exception as exc:  # noqa: BLE001
            print(f"(area-risk model unavailable: {exc})\n")

        tourists = db.execute(select(Tourist)).scalars().all()
        all_points: list[tuple[float, float]] = []

        for t in tourists:
            pings = db.execute(
                select(LocationPing)
                .where(LocationPing.tourist_id == t.id)
                .order_by(LocationPing.recorded_at)
            ).scalars().all()
            if not pings:
                continue

            last = pings[-1]
            lat, lon = geom_to_shape(last.geom).y, geom_to_shape(last.geom).x
            all_points.extend(
                (geom_to_shape(p.geom).y, geom_to_shape(p.geom).x) for p in pings
            )

            print(f"=== {t.display_name} ({len(pings)} pings) ===")

            signals = []
            signals += check_geofence(lat, lon, zones)

            if t.planned_route is not None:
                route = list(geom_to_shape(t.planned_route).coords)  # (lon, lat)
                dev = check_route_deviation(lat, lon, route)
                if dev:
                    signals.append(dev)

            gap_s = (now - last.recorded_at).total_seconds()
            zrisk = _risk_category_at(lat, lon, zones)
            inact = check_inactivity(gap_s, zrisk)
            if inact:
                signals.append(inact)

            if predict_risk:
                score = predict_risk(lat, lon, now)
                print(f"  area-risk score @ last position: {score:.3f}")

            if signals:
                for s in signals:
                    print(f"  [{s.severity.value.upper():8s}] {s.reason}")
            else:
                print("  no detection signals")
            print()

        # Crowd density: real aggregation (counts are low for seed data), plus an
        # illustrative burst to show the detector firing.
        print("=== Crowd density ===")
        gh = aggregate_by_geohash(all_points, precision=7)
        hottest = max(gh.items(), key=lambda kv: kv[1]) if gh else (None, 0)
        print(f"  geohash cells: {len(gh)}; hottest {hottest[0]} = {hottest[1]} pings")
        for name, cap in zone_caps.items():
            if not cap:
                continue
            sig = check_zone_crowd(int(cap * 0.05), cap, zone_name=name)
            status = sig.reason if sig else f"OK (cap {cap})"
            print(f"  {name:32s}: {status}")
        burst = check_zone_crowd(950, 1000, zone_name="(illustrative) Festival Ground")
        print(f"  illustrative burst -> [{burst.severity.value.upper()}] {burst.reason}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
