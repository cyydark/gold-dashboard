"""Alert management API routes."""
from fastapi import APIRouter
from backend.data.db import get_all_rules, add_rule, delete_rule
from backend.data.models import AlertCreate

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/")
async def list_alerts():
    """List all active alert rules."""
    rules = await get_all_rules()
    return [{"id": r["id"], "symbol": r["symbol"],
             "high_price": r["high_price"], "low_price": r["low_price"],
             "condition": r["condition"]} for r in rules]


@router.post("/")
async def create_alert(payload: AlertCreate):
    """Create a new alert rule."""
    if payload.high_price is None and payload.low_price is None:
        return {"error": "至少需要设置一个价格阈值"}

    rule_id = await add_rule(
        symbol=payload.symbol,
        high_price=payload.high_price,
        low_price=payload.low_price,
        condition=payload.condition,
    )
    return {"id": rule_id, "message": "预警规则已创建"}


@router.delete("/{rule_id}")
async def remove_alert(rule_id: int):
    """Delete (deactivate) an alert rule."""
    success = await delete_rule(rule_id)
    return {"success": success, "message": "预警已删除" if success else "未找到该预警"}
