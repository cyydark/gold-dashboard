"""Briefing API routes."""
from fastapi import APIRouter, Depends
from backend.services.briefing_service import BriefingService
from backend.api.dependencies import get_briefing_service

router = APIRouter(prefix="/api", tags=["briefings"])


@router.get("/briefings")
async def get_briefings(days: int = 7,
                        service: BriefingService = Depends(get_briefing_service)):
    """Return weekly briefing + recent news list."""
    return await service.get_briefings(days)


@router.post("/briefings/trigger")
async def trigger_briefing(service: BriefingService = Depends(get_briefing_service)):
    """Manually trigger briefing generation."""
    await service.trigger_briefing_generation()
    return {"status": "done"}
