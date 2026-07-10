import logging

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.services.daily_challenge import run_daily_push

logger = logging.getLogger("hibi_bot.internal")

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/push-daily")
async def push_daily(x_cron_secret: str = Header(None)):
    if not x_cron_secret or x_cron_secret != settings.internal_cron_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = run_daily_push()
    logger.info("push-daily result: %s", result)
    return result
