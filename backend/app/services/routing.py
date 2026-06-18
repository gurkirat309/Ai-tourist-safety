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


def compute_route(
    start_lat: float, start_lon: float, dest_lat: float, dest_lon: float
) -> Route:
    """Real road route via OSRM; falls back to a straight line on any failure."""
    start = (start_lon, start_lat)
    dest = (dest_lon, dest_lat)
    url = f"{OSRM_URL}/{start_lon},{start_lat};{dest_lon},{dest_lat}"
    params = {"overview": "full", "geometries": "geojson"}
    try:
        import httpx

        from app.services.tls import ensure_system_tls

        ensure_system_tls()
        resp = httpx.get(url, params=params, timeout=_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"OSRM code={data.get('code')}")
        route = data["routes"][0]
        coords = [(c[0], c[1]) for c in route["geometry"]["coordinates"]]
        return Route(
            coords=coords,
            distance_m=float(route["distance"]),
            duration_s=float(route["duration"]),
            source="osrm",
        )
    except Exception as exc:  # noqa: BLE001
        log.info("OSRM unavailable (%s); using straight-line route", exc)
        return _straight_line(start, dest)
