"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from vaad import __version__
from vaad.config import Settings
from vaad.server.routes import router


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="vaad", version=__version__)
    app.state.settings = settings
    app.include_router(router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


# For `uvicorn vaad.server.app:app` during development (no backend configured).
app = create_app()
