"""Place suggestions + geocoding for trip planning.

Provides a curated list of popular Bengaluru destinations (instant, offline) and
free-text geocoding via the public OpenStreetMap Nominatim API (graceful: returns
[] if unreachable). Coordinates are (lat, lon).
"""

from __future__ import annotations

from app.core.logging import get_logger

log = get_logger(__name__)

# Curated tourist-relevant places in/around Bengaluru.
# (name, lat, lon, category)
BENGALURU_PLACES = [
    ("Cubbon Park", 12.9763, 77.5929, "park"),
    ("Lalbagh Botanical Garden", 12.9507, 77.5848, "park"),
    ("Bangalore Palace", 12.9988, 77.5921, "landmark"),
    ("Vidhana Soudha", 12.9794, 77.5907, "landmark"),
    ("MG Road", 12.9750, 77.6090, "shopping"),
    ("Commercial Street", 12.9824, 77.6090, "shopping"),
    ("UB City Mall", 12.9719, 77.5963, "shopping"),
    ("ISKCON Temple", 13.0098, 77.5510, "temple"),
    ("Bull Temple (Dodda Basavana Gudi)", 12.9426, 77.5676, "temple"),
    ("Tipu Sultan's Summer Palace", 12.9591, 77.5739, "landmark"),
    ("HAL Aerospace Museum", 12.9507, 77.6680, "museum"),
    ("Indiranagar", 12.9719, 77.6412, "nightlife"),
    ("Koramangala", 12.9352, 77.6245, "nightlife"),
    ("Majestic (Kempegowda Bus Stand)", 12.9770, 77.5720, "transit"),
    ("Bannerghatta National Park", 12.8000, 77.5770, "nature"),
    ("Nandi Hills", 13.3702, 77.6835, "nature"),
]


def curated_places() -> list[dict]:
    return [
        {"name": n, "lat": lat, "lon": lon, "category": cat}
        for (n, lat, lon, cat) in BENGALURU_PLACES
    ]


def geocode(query: str, limit: int = 6) -> list[dict]:
    """Free-text place search via Nominatim, biased to the Bengaluru area."""
    query = query.strip()
    if len(query) < 3:
        return []
    try:
        import httpx

        from app.services.tls import ensure_system_tls

        ensure_system_tls()
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "json",
                "limit": limit,
                "countrycodes": "in",
                # Bias toward Bengaluru (viewbox lon,lat corners).
                "viewbox": "77.35,13.20,77.85,12.70",
            },
            headers={"User-Agent": "tourist-safety-demo/0.1"},
            timeout=6.0,
        )
        resp.raise_for_status()
        out = []
        for r in resp.json():
            out.append({
                "name": r.get("display_name", query).split(",")[0],
                "full_name": r.get("display_name"),
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "category": r.get("type", "place"),
            })
        return out
    except Exception as exc:  # noqa: BLE001
        log.info("Geocode failed for %r: %s", query, exc)
        return []
