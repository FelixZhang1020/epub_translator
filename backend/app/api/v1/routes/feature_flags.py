"""Feature flags API routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter()


class FeatureFlags(BaseModel):
    """Feature flags exposed to the frontend."""

    enable_epub_export: bool


@router.get("/feature-flags", response_model=FeatureFlags)
async def get_feature_flags() -> FeatureFlags:
    """Get feature flags for the frontend."""
    return FeatureFlags(
        enable_epub_export=settings.enable_epub_export,
    )
