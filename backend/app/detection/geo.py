"""Geo helpers for the detection layer.

Distances are returned in **meters**. We use Shapely for geometric projection
(nearest point on a route) and geopy's geodesic for the accurate metric, since
Shapely distances are planar degrees, not meters.
"""

from __future__ import annotations

from geopy.distance import geodesic
from shapely.geometry import LineString, Point


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Geodesic distance between two lat/lon points, in meters."""
    return float(geodesic((lat1, lon1), (lat2, lon2)).meters)


def distance_point_to_route_m(
    lat: float, lon: float, route: list[tuple[float, float]]
) -> float:
    """Geodesic distance (m) from a point to its nearest point on a route.

    `route` is a list of (lon, lat) pairs (GeoJSON order).
    """
    if not route:
        raise ValueError("route must have at least one coordinate")
    if len(route) == 1:
        rlon, rlat = route[0]
        return distance_m(lat, lon, rlat, rlon)

    line = LineString(route)
    pt = Point(lon, lat)
    # Nearest point on the line (planar projection, fine for finding the spot).
    nearest = line.interpolate(line.project(pt))
    return distance_m(lat, lon, nearest.y, nearest.x)
