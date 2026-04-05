import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.presentation.api.routes import router

_DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:3000"


def create_app() -> FastAPI:
    app = FastAPI(
        title="LetterCatcher API",
        description="REST API for LetterCatcher email monitoring service",
        version="1.0.0",
    )

    raw = os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS)
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")
    return app
