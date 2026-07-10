import base64
import hashlib
import hmac
import logging
from urllib.parse import parse_qsl

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.services import menu_actions
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


def _handle_postback(event: dict) -> None:
    line_user_id = event["source"]["userId"]
    params = dict(parse_qsl(event["postback"]["data"]))
    action = params.pop("action", None)
    mode = params.get("mode")
    reply_token = event["replyToken"]

    user_id = get_or_create_user(line_user_id)
    log_menu_interaction(user_id=user_id, action=action, mode=mode)
    menu_actions.dispatch(action, params, user_id, reply_token)


def _handle_message(event: dict) -> None:
    if event.get("message", {}).get("type") != "text":
        return

    line_user_id = event["source"]["userId"]
    text = event["message"]["text"]
    reply_token = event["replyToken"]

    user_id = get_or_create_user(line_user_id)
    handle_text_message(user_id, text, reply_token)


@router.post("")
async def line_webhook(request: Request, x_line_signature: str = Header(None)):
    body = await request.body()

    if not x_line_signature or not _verify_signature(body, x_line_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    for event in payload.get("events", []):
        logger.info("Received LINE event: %s", event)
        if event.get("type") == "postback":
            _handle_postback(event)
        elif event.get("type") == "message":
            _handle_message(event)

    return "OK"
