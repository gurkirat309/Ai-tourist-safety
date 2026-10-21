"""FastAPI application entrypoint."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    health,
    incidents,
    locations,
    me,
    places,
    police,
    risk,
    tourists,
    voice,
)
from app.api.spa import mount_spa
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log.info("Starting %s (env=%s)", settings.app_name, settings.env)
    yield
    log.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tourist Safety API",
        description=(
            "Backend for the AI-Orchestrated Multi-Agent System for Tourist "
            "Safety and Incident Intelligence. No UI — APIs only."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # The tourist PWA and police dashboard are served from their own origins,
    # so browsers need an explicit CORS grant. Origins come from the env
    # (CORS_ORIGINS) so production never has to allow a dev host.
    settings = get_settings()
    origins = settings.cors_origin_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        # Credentials cannot be combined with a wildcard origin.
        allow_credentials="*" not in origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(places.router)
    app.include_router(tourists.router)
    app.include_router(locations.router)
    app.include_router(risk.router)
    app.include_router(incidents.router)
    app.include_router(police.router)
    app.include_router(voice.router)
    app.include_router(voice.router, prefix="/api")

    # Mounted LAST so every API route above wins the match. No-op when
    # the app hasn't been built.
    if settings.serve_app:
        dist = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", settings.app_dist_dir)
        )
        mount_spa(app, dist)

    return app


app = create_app()
