import base64
import hashlib
import hmac
import logging
from urllib.parse import parse_qsl

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.services import line_client, menu_actions
from app.services.menu_interaction import log_menu_interaction
from app.services.message_router import handle_text_message
from app.services.users import get_or_create_user

logger = logging.getLogger("hibi_bot.webhook")

router = APIRouter(prefix="/webhook", tags=["webhook"])


def _verify_signature(body: bytes, signature: str) -> bool:
    expected = base64.b64encode(
        hmac.new(settings.line_channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def _fallback_reply(reply_token: str) -> None:
    """任何未預期的例外都會走到這裡。沒有這一層的話，使用者會完全收不到任何回覆
    （LINE 端就是已讀不回的狀態），對一個以「降低練習焦慮」為目標的工具來說是最壞的
    失敗方式。這裡本身失敗（例如 reply_token 已經被上游用掉）也只記錄、不往外丟，
    避免例外處理本身又造成新的未捕捉例外。
    """
    try:
        line_client.reply_text(reply_token, "系統剛剛出了一點小狀況，請稍後再試一次；如果持續發生，麻煩告訴授課老師。")
    except Exception:
        logger.exception("Fallback reply itself also failed")


def _handle_postback(event: dict) -> None:
    reply_token = event["replyToken"]
    try:
        line_user_id = event["source"]["userId"]
        params = dict(parse_qsl(event["postback"]["data"]))
        action = params.pop("action", None)
        mode = params.get("mode")

        user_id = get_or_create_user(line_user_id)
        log_menu_interaction(user_id=user_id, action=action, mode=mode)
        menu_actions.dispatch(action, params, user_id, reply_token)
    except Exception:
        logger.exception("Unhandled error handling postback event: %s", event)
        _fallback_reply(reply_token)


def _handle_message(event: dict) -> None:
    if event.get("message", {}).get("type") != "text":
        return

    reply_token = event["replyToken"]
    try:
        line_user_id = event["source"]["userId"]
        text = event["message"]["text"]

        user_id = get_or_create_user(line_user_id)
        handle_text_message(user_id, text, reply_token)
    except Exception:
        logger.exception("Unhandled error handling message event: %s", event)
        _fallback_reply(reply_token)


@router.post("")
async def line_webhook(request: Request, x_line_signature: str = Header(None)):
    body = await request.body()

    if not x_line_signature or not _verify_signature(body, x_line_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    for event in payload.get("events", []):
        logger.info("Received LINE event: %s", event)
        # _handle_postback/_handle_message 內部都是同步阻塞呼叫（Supabase、OpenAI 的
        # client 都不是 async 的）。丟進 run_in_threadpool 讓事件迴圈不會被單一使用者的
        # 這次互動整個卡住，才能真正同時處理多個使用者同時傳來的請求。單一請求內的多個
        # event 仍然依序 await（維持同一次 webhook 呼叫內的處理順序），只有跨請求之間
        # 才會真正並行。
        if event.get("type") == "postback":
            await run_in_threadpool(_handle_postback, event)
        elif event.get("type") == "message":
            await run_in_threadpool(_handle_message, event)

    return "OK"
