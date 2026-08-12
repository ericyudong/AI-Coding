"""Background scheduler for performance alert refresh + email dispatch."""
from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services import performance_service as svc

logger = logging.getLogger(__name__)
_task: asyncio.Task | None = None


async def _loop() -> None:
    settings = get_settings()
    interval = max(60, int(settings.performance_alert_interval_seconds or 900))
    while True:
        try:
            async with SessionLocal() as db:
                created = await svc.refresh_alerts(db, user=None)
                logger.info("alert scheduler: created=%s", created)
        except Exception:  # noqa: BLE001
            logger.exception("alert scheduler failed")
        await asyncio.sleep(interval)


def start_alert_scheduler() -> None:
    global _task
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_loop())


async def stop_alert_scheduler() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
