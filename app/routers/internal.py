from fastapi import APIRouter

router = APIRouter(prefix="/internal", tags=["internal"])

# 供 Railway Cron Job 呼叫的內部端點，實際推播邏輯留待 Phase 5 實作。
