"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.database.base import init_db
from app.api.v1.routes import upload, translation, preview, export, llm_settings, workflow, analysis, reference, proofreading, prompts
from app.api.dependencies import sync_projects_on_startup

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: Initialize database
    await init_db()

    # Startup: Sync projects (clean up orphaned records)
    try:
        summary = await sync_projects_on_startup()
        if summary["db_records_deleted"] > 0:
            logger.info(
                "Cleaned up %d orphaned project records on startup",
                summary["db_records_deleted"],
            )
        if summary["orphaned_folders_found"] > 0:
            logger.warning(
                "Found %d orphaned project folders: %s",
                summary["orphaned_folders_found"],
                summary["orphaned_folder_ids"],
            )
    except Exception as e:
        logger.error("Failed to sync projects on startup: %s", e)

    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title=settings.app_name,
    description="ePub Translation Tool with LLM support",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router, prefix="/api/v1", tags=["upload"])
app.include_router(translation.router, prefix="/api/v1", tags=["translation"])
app.include_router(preview.router, prefix="/api/v1", tags=["preview"])
app.include_router(export.router, prefix="/api/v1", tags=["export"])
app.include_router(llm_settings.router, prefix="/api/v1", tags=["settings"])
app.include_router(workflow.router, prefix="/api/v1", tags=["workflow"])
app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])
app.include_router(reference.router, prefix="/api/v1", tags=["reference"])
app.include_router(proofreading.router, prefix="/api/v1", tags=["proofreading"])
app.include_router(prompts.router, prefix="/api/v1", tags=["prompts"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "ePub Translator API", "version": "0.1.0"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
