"""Alert status endpoint."""

from fastapi import APIRouter, Depends, Query

from ..alerts import manager
from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..models import AlertsStatus

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/alerts", response_model=AlertsStatus)
async def get_alerts(
    refresh: bool = Query(False, description="Re-evaluate now instead of cached."),
    registry: InstanceRegistry = Depends(get_registry),
) -> AlertsStatus:
    settings = get_settings()
    alerts = manager.alerts
    if refresh:
        alerts = await manager.evaluate(registry, settings)
    return AlertsStatus(
        webhook_configured=bool(settings.alert_webhook),
        interval=settings.alert_interval,
        alerts=alerts,
    )
