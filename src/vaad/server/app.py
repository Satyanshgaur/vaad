"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vaad import __version__
from vaad.config import Settings
from vaad.server.backend import BackendClient
from vaad.server.routes import router


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        if app.state.small is not None:
            await app.state.small.aclose()

    app = FastAPI(title="vaad", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.small = BackendClient(settings.small) if settings else None
    app.include_router(router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


# For `uvicorn vaad.server.app:app` during development (no backend configured).
app = create_app()
