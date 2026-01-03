"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger
from pathlib import Path

from app.api import api_router
from app.core import get_settings, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    setup_logging()
    logger.info("Starting Smart RAG application")
    
    # Clear database on startup for fresh state
    try:
        from app.core import get_neo4j_repository
        async for repo in get_neo4j_repository():
            await repo.clear_all()
            logger.info("Database cleared on startup - starting with fresh state")
            break
    except Exception as e:
        logger.warning(f"Could not clear database on startup: {e}")

    yield

    # Shutdown - also clear database
    logger.info("Shutting down Smart RAG application")
    try:
        from app.core import get_neo4j_repository
        async for repo in get_neo4j_repository():
            await repo.clear_all()
            logger.info("Database cleared on shutdown")
            break
    except Exception as e:
        logger.warning(f"Could not clear database on shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Smart RAG",
    description="Hierarchical Graph-of-Graphs RAG System",
    version="0.1.0",
    lifespan=lifespan,
)

# Get settings
settings = get_settings()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.api_v1_prefix)

# Mount static files
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/")
async def root():
    """Serve the web interface."""
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app_debug,
        log_level=settings.log_level.lower(),
    )
