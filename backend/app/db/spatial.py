"""Conversions between Shapely geometries / lat-lon and PostGIS (GeoAlchemy2).

Centralizes SRID 4326 handling so models, seed scripts, and services don't
re-implement WKT/WKB juggling.
"""

from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

SRID = 4326


def point_to_geom(lat: float, lon: float) -> WKBElement:
    """lat/lon -> PostGIS POINT (note: Shapely uses (x=lon, y=lat))."""
    return from_shape(Point(lon, lat), srid=SRID)


def linestring_to_geom(coords: list[tuple[float, float]]) -> WKBElement:
    """List of (lon, lat) pairs -> PostGIS LINESTRING."""
    return from_shape(LineString(coords), srid=SRID)


def polygon_to_geom(coords: list[tuple[float, float]]) -> WKBElement:
    """List of (lon, lat) pairs (outer ring) -> PostGIS POLYGON."""
    return from_shape(Polygon(coords), srid=SRID)


def geom_to_shape(geom: WKBElement) -> BaseGeometry:
    """PostGIS geometry -> Shapely geometry."""
    return to_shape(geom)


def geom_to_latlon(geom: WKBElement) -> tuple[float, float]:
    """PostGIS POINT -> (lat, lon)."""
    pt = to_shape(geom)
    return (pt.y, pt.x)
