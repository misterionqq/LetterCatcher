from fastapi import FastAPI
from src.presentation.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="LetterCatcher API",
        description="REST API for LetterCatcher email monitoring service",
        version="1.0.0",
    )
    app.include_router(router, prefix="/api/v1")
    return app
