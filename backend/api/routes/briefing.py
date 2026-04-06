"""Briefing API routes."""
from fastapi import APIRouter, Depends, Request, Query
from backend.services.briefing_service import BriefingService
from backend.api.dependencies import get_briefing_service
from backend.api.limiter import limiter

router = APIRouter(prefix="/api", tags=["briefings"])


@router.get("/briefings")
async def get_briefings(days: int = Query(default=7, ge=1, le=30),
                        service: BriefingService = Depends(get_briefing_service)):
    """Return weekly briefing + recent news list."""
    return await service.get_briefings(days)


@router.post("/briefings/trigger")
@limiter.limit("3/hour")
async def trigger_briefing(request: Request,
                          service: BriefingService = Depends(get_briefing_service)):
    """Manually trigger briefing generation (rate limited: 3/hour)."""
    await service.trigger_briefing_generation()
    return {"status": "done"}
