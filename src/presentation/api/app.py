import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.presentation.api.routes import router
from src.presentation.api.rate_limit import limiter

_DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:3000"


def create_app() -> FastAPI:
    app = FastAPI(
        title="LetterCatcher API",
        description="REST API for LetterCatcher email monitoring service",
        version="1.0.0",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
