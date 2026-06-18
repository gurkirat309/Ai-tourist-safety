"""Place suggestions + search for trip planning (public reference data)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.services.places import curated_places, geocode

router = APIRouter(prefix="/places", tags=["places"])


@router.get("")
def suggestions() -> dict[str, Any]:
    """Curated, popular Bengaluru destinations for the picker."""
    return {"places": curated_places()}


@router.get("/search")
def search(q: str = Query(min_length=3)) -> dict[str, Any]:
    """Free-text place search (geocoding); [] if the geocoder is unreachable."""
    return {"results": geocode(q)}
