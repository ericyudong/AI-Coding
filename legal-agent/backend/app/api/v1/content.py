"""Home and content API."""
from fastapi import APIRouter

from app.schemas.schemas import AiModuleCard, NewsItem, QuickLink
from app.services.content_service import (
    AI_MODULES,
    DRAFT_STYLES,
    LABOR_EXAMPLES,
    NEWS_ITEMS,
    QUICK_LINKS,
    SEARCH_SUGGESTIONS,
    SEARCH_TYPES,
)

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/quick-links", response_model=list[QuickLink])
async def quick_links():
    return QUICK_LINKS


@router.get("/ai-modules", response_model=list[AiModuleCard])
async def ai_modules():
    return AI_MODULES


@router.get("/news", response_model=list[NewsItem])
async def news(category: str | None = None):
    if category:
        return [n for n in NEWS_ITEMS if n.category == category]
    return NEWS_ITEMS


@router.get("/search-suggestions")
async def search_suggestions():
    return {"items": SEARCH_SUGGESTIONS}


@router.get("/labor-examples")
async def labor_examples():
    return {"items": LABOR_EXAMPLES}


@router.get("/search-types")
async def search_types():
    return {"items": SEARCH_TYPES}


@router.get("/draft-styles")
async def draft_styles():
    return {"items": DRAFT_STYLES}
