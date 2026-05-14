from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.config import settings
from app.rag.indexer import DEFAULT_INDEX_PATH


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> FastAPI:
    application = FastAPI(
        title="DataOps OnCall Agent",
        version="0.1.0",
        description="Local MVP API for DataOps incident diagnosis demos.",
    )
    application.state.database_url = settings.database_url
    application.state.rag_index_path = DEFAULT_INDEX_PATH
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/", include_in_schema=False)
    def demo_ui() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return application


app = create_app()
