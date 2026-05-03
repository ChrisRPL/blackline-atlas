from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings
from app.services.stub import StubAtlasService

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
UI_INDEX_PATH = Path(__file__).resolve().parent.parent / "ui" / "index.html"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Blackline Atlas",
        version="0.1.0",
        description="Onboard civilian lifeline monitoring scaffold.",
    )
    app.state.atlas_service = StubAtlasService(settings=settings)
    app.include_router(router)
    app.mount("/ui-static", StaticFiles(directory=UI_DIR), name="ui-static")

    @app.middleware("http")
    async def no_store_ui_assets(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path in {"/ui", "/ui/"} or path.startswith("/ui-static/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.get("/ui", include_in_schema=False)
    @app.get("/ui/", include_in_schema=False)
    def ui_shell() -> FileResponse:
        return FileResponse(UI_INDEX_PATH)

    return app


app = create_app()
