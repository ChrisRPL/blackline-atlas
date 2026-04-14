from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings
from app.services.stub import StubAtlasService


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Blackline Atlas",
        version="0.1.0",
        description="Onboard civilian lifeline monitoring scaffold.",
    )
    app.state.atlas_service = StubAtlasService(settings=settings)
    app.include_router(router)
    return app


app = create_app()
