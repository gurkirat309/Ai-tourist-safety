"""Serve the built tourist PWA from the API, on a single origin.

Why this exists: phones only expose geolocation on secure (https) origins, so
testing on a real device needs a tunnel. Serving the app and the API from one
host means **one** tunnel instead of two, and no CORS at all — the app's
requests become same-origin.

This is opt-in. If the build directory is missing, nothing is mounted and the
API behaves exactly as before, so `uv run uvicorn app.main:app` still works
with no frontend built.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

log = get_logger(__name__)

# Paths owned by the API. A request starting with one of these is never
# answered with the SPA shell, so a typo'd API call still returns a clean 404
# instead of a page of HTML.
API_PREFIXES = (
    "/health", "/auth", "/me", "/places", "/tourists", "/locations",
    "/risk", "/incidents", "/alerts", "/police", "/voice", "/api",
    "/docs", "/redoc", "/openapi.json",
)


class SpaStaticFiles(StaticFiles):
    """StaticFiles that falls back to index.html for client-side routes.

    The app uses history routing, so /trip and /map are real URLs the user can
    open or reload. They have no file on disk and must return the shell.
    """

    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except Exception:
            # `path` arrives relative to the mount, so compare with a leading
            # slash restored.
            full = "/" + path.lstrip("/")
            # An unmatched API path must stay a real 404. Returning the shell
            # would hand the caller HTML to parse as JSON and make a typo'd
            # endpoint look like a success.
            if full.startswith(API_PREFIXES):
                raise
            index = os.path.join(self.directory, "index.html")
            if os.path.isfile(index):
                return FileResponse(index)
            raise


def mount_spa(app: FastAPI, dist_dir: str) -> bool:
    """Mount the built PWA at `/`. Returns True if it was actually mounted."""
    if not os.path.isdir(dist_dir) or not os.path.isfile(
        os.path.join(dist_dir, "index.html")
    ):
        log.info(
            "Tourist app not mounted (no build at %s). "
            "Build it with: cd mobile && npm run build",
            dist_dir,
        )
        return False

    @app.middleware("http")
    async def _never_cache_the_shell(request: Request, call_next):
        """Keep index.html fresh so a rebuilt app isn't masked by a stale shell.

        Hashed assets under /assets are immutable and stay cacheable.
        """
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.mount("/", SpaStaticFiles(directory=dist_dir, html=True), name="tourist-app")
    log.info("Tourist app mounted at / from %s", dist_dir)
    return True
