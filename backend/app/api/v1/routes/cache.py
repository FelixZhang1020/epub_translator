"""Cache management API routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db, Project
from app.core.cache.llm_cache import get_cache
from app.api.dependencies import ValidatedProject

router = APIRouter()


class CacheStatsResponse(BaseModel):
    """Cache statistics response."""
    project_id: str
    total_entries: int
    expired_entries: int
    active_entries: int
    total_size_mb: float
    total_accesses: int
    avg_accesses_per_entry: float
    oldest_entry_age_days: float
    newest_entry_age_days: float


class CacheClearResponse(BaseModel):
    """Cache clear response."""
    project_id: str
    entries_deleted: int
    action: str


@router.get("/cache/{project_id}/stats")
async def get_cache_stats(
    project: ValidatedProject,
) -> CacheStatsResponse:
    """Get cache statistics for a project.

    Returns detailed statistics about the LLM response cache including:
    - Number of cached entries (total, active, expired)
    - Total cache size in MB
    - Access patterns
    - Age of oldest/newest entries
    """
    # Get cache statistics
    cache = get_cache(project.id)
    stats = cache.get_stats()

    return CacheStatsResponse(
        project_id=project.id,
        **stats
    )


@router.post("/cache/{project_id}/clear")
async def clear_cache(
    project: ValidatedProject,
) -> CacheClearResponse:
    """Clear all cache entries for a project.

    This will delete all cached LLM responses. Subsequent translations
    will make fresh API calls until the cache is rebuilt.
    """
    # Clear cache
    cache = get_cache(project.id)
    count = cache.clear_all()

    return CacheClearResponse(
        project_id=project.id,
        entries_deleted=count,
        action="clear_all"
    )


@router.post("/cache/{project_id}/clear-expired")
async def clear_expired_cache(
    project: ValidatedProject,
) -> CacheClearResponse:
    """Clear expired cache entries for a project.

    This will only delete cache entries that have exceeded their TTL.
    Active cache entries are preserved.
    """
    # Clear expired entries
    cache = get_cache(project.id)
    count = cache.clear_expired()

    return CacheClearResponse(
        project_id=project.id,
        entries_deleted=count,
        action="clear_expired"
    )


@router.get("/cache/stats/all")
async def get_all_cache_stats(
    db: AsyncSession = Depends(get_db),
) -> list[CacheStatsResponse]:
    """Get cache statistics for all projects.

    Returns cache statistics for every project in the database.
    Useful for monitoring overall cache usage and efficiency.
    """
    # Get all projects
    result = await db.execute(select(Project))
    projects = result.scalars().all()

    stats_list = []
    for project in projects:
        cache = get_cache(project.id)
        stats = cache.get_stats()

        stats_list.append(CacheStatsResponse(
            project_id=project.id,
            **stats
        ))

    return stats_list
