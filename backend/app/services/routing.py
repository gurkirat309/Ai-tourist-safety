"""Route computation from a start to a destination.

Uses the public OSRM API for real road geometry, with a straight-line fallback
so the feature works offline / when OSRM is unreachable. Coordinates are
(lon, lat) pairs (GeoJSON order) throughout.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.detection.geo import distance_m

log = get_logger(__name__)

OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
_TIMEOUT_S = 8.0


@dataclass
class Route:
    coords: list[tuple[float, float]]  # (lon, lat)
    distance_m: float
    duration_s: float
    source: str  # "osrm" | "straightline"


def _straight_line(
    start: tuple[float, float], dest: tuple[float, float]
) -> Route:
    (slon, slat), (dlon, dlat) = start, dest
    d = distance_m(slat, slon, dlat, dlon)
    return Route(
        coords=[start, dest],
        distance_m=d,
        duration_s=d / 1.4,  # ~walking pace
        source="straightline",
    )


def compute_routes(
    start_lat: float,
    start_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    alternatives: int = 3,
) -> list[Route]:
    """Up to `alternatives` distinct road routes via OSRM, fastest first.

    Asking for alternatives is what makes a *safer* route possible: with only
    one candidate there is nothing to compare. OSRM may still return a single
    route when no genuine alternative exists, so callers must handle a
    one-element list.

    Always returns at least one route — a straight line if OSRM is
    unreachable — so trip planning never hard-fails.
    """
    start = (start_lon, start_lat)
    dest = (dest_lon, dest_lat)
    url = f"{OSRM_URL}/{start_lon},{start_lat};{dest_lon},{dest_lat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        # OSRM accepts a count; it returns fewer when none are meaningfully
        # different.
        "alternatives": str(max(1, alternatives)),
    }
    try:
        import httpx

        from app.services.tls import ensure_system_tls

        ensure_system_tls()
        resp = httpx.get(url, params=params, timeout=_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"OSRM code={data.get('code')}")

        routes: list[Route] = []
        for route in data["routes"][:alternatives]:
            coords = [(c[0], c[1]) for c in route["geometry"]["coordinates"]]
            if not coords:
                continue
            routes.append(
                Route(
                    coords=coords,
                    distance_m=float(route["distance"]),
                    duration_s=float(route["duration"]),
                    source="osrm",
                )
            )
        if not routes:
            raise ValueError("OSRM returned no usable geometry")
        return routes
    except Exception as exc:  # noqa: BLE001
        log.info("OSRM unavailable (%s); using straight-line route", exc)
        return [_straight_line(start, dest)]


def compute_route(
    start_lat: float, start_lon: float, dest_lat: float, dest_lon: float
) -> Route:
    """The single fastest road route (thin wrapper over `compute_routes`)."""
    return compute_routes(
        start_lat, start_lon, dest_lat, dest_lon, alternatives=1
    )[0]
