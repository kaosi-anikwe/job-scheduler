"""FastAPI application factory and lifespan management.

Initialises database engine, Redis pool, and WebSocket Redis listener on
startup. Cleans up all resources on shutdown.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import dlq, health, jobs, workers
from api.websocket.manager import manager
from shared.config import get_settings
from shared.database import dispose_engine, get_engine
from shared.logging import setup_logging
from shared.redis import close_redis, get_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle for the FastAPI app."""
    # -- Startup --
    setup_logging()

    # Warm up connections
    get_engine()
    await get_redis()

    # Start WebSocket Redis listener
    await manager.start_redis_listener()

    yield

    # -- Shutdown --
    await manager.stop_redis_listener()
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Job Scheduler",
        description="Production-grade background job scheduler with DAG workflows",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # -- CORS --
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Routers --
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])
    app.include_router(dlq.router, prefix="/api/v1", tags=["Dead-Letter Queue"])
    app.include_router(workers.router, prefix="/api/v1", tags=["Workers"])

    # -- WebSocket --
    from api.websocket.manager import websocket_endpoint

    app.add_api_websocket_route("/ws/jobs", websocket_endpoint)

    return app


app = create_app()
