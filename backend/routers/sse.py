"""Server-Sent Events (SSE) for real-time price streaming."""
import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from backend.data.sources.international import fetch_xauusd, fetch_usdcny
from backend.data.sources.domestic import fetch_au9999

router = APIRouter(tags=["sse"])

PRICE_INTERVAL = 30  # 30s


async def price_generator():
    """Yield SSE events with current prices every PRICE_INTERVAL seconds."""
    while True:
        payload = {}
        updated = ""

        loop = asyncio.get_event_loop()
        xau, au9999, usdcny = await asyncio.gather(
            loop.run_in_executor(None, fetch_xauusd),
            fetch_au9999(),
            loop.run_in_executor(None, fetch_usdcny),
        )

        if xau:
            payload["XAUUSD"] = xau
            updated = xau.get("updated_at", "")
        if au9999:
            payload["AU9999"] = au9999
            if not updated:
                updated = au9999.get("updated_at", "")
        if usdcny:
            payload["USDCNY"] = usdcny
            if not updated:
                updated = usdcny.get("updated_at", "")

        payload["updated_at"] = updated
        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(PRICE_INTERVAL)


@router.get("/stream")
async def stream_prices():
    return StreamingResponse(
        price_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
