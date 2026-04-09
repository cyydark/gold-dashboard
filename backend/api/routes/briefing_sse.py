"""SSE 流式金价分析 endpoint."""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.services.briefing_service import briefing_stream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["briefings"])


@router.get("/briefings/stream")
async def get_briefing_stream(days: int = Query(default=3, ge=1, le=30)):
    """SSE 流式金价分析。缓存命中时返回 event:cached。"""

    async def sse_generator():
        try:
            async for ev in briefing_stream(days):
                if ev["type"] == "cached":
                    blocks = ev.get("blocks", ev)
                    yield f"event: cached\ndata: {json.dumps({'blocks': blocks}, ensure_ascii=False)}\n\n"
                elif ev["type"] == "token":
                    yield f"event: token\ndata: {json.dumps({'block': ev['block'], 'chunk': ev['chunk']}, ensure_ascii=False)}\n\n"
                elif ev["type"] == "block-done":
                    yield f"event: block-done\ndata: {json.dumps({'block': ev['block']}, ensure_ascii=False)}\n\n"
                elif ev["type"] == "done":
                    yield f"event: done\ndata: {json.dumps({'blocks': ev['blocks']}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
