"""Geo primitives for API I/O.

Points are exposed as simple {lat, lon} objects (WGS84). Polylines/polygons are
lists of [lon, lat] pairs (GeoJSON coordinate order). Conversion to/from PostGIS
geometry lives in `app.db.spatial`.
"""

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


# A coordinate is [lon, lat] (GeoJSON order).
Coordinate = tuple[float, float]
