"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, incidents, locations, risk, tourists
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

    app.include_router(health.router)
    app.include_router(tourists.router)
    app.include_router(locations.router)
    app.include_router(risk.router)
    app.include_router(incidents.router)
    return app


app = create_app()
