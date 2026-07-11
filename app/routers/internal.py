import logging

from fastapi import APIRouter, Header, HTTPException
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.services.daily_challenge import run_daily_push

logger = logging.getLogger("hibi_bot.internal")

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/push-daily")
async def push_daily(x_cron_secret: str = Header(None)):
    if not x_cron_secret or x_cron_secret != settings.internal_cron_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # run_daily_push 是同步阻塞呼叫，且會依序迴圈每一位使用者做 DB 查詢＋LINE 推播；
    # 丟進 run_in_threadpool 避免這段（推播當下往往也是使用者最集中湧入的時間點）把
    # 事件迴圈整個卡住、連帶讓同時進來的真實互動請求被排隊卡住。
    result = await run_in_threadpool(run_daily_push)
    logger.info("push-daily result: %s", result)
    return result
