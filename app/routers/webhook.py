import base64
import hashlib
import hmac
import logging
from urllib.parse import parse_qsl

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.services import access_codes, email_client, line_client, menu_actions
from app.services.menu_interaction import log_menu_interaction
from app.services.message_router import handle_text_message
from app.services.session_state import clear_session_state, get_session_state
from app.services.users import get_or_create_user

logger = logging.getLogger("hibi_bot.webhook")

router = APIRouter(prefix="/webhook", tags=["webhook"])

# 這些互動會呼叫 AI 生成解析／回覆，等待感明顯，才需要顯示「輸入中」動畫；「下一題」
# 「查進度」這類幾乎瞬間回覆的動作動畫只會一閃即逝，體驗上沒有差別，故意不套用。
SLOW_POSTBACK_ACTIONS = {"answer", "review_answer", "daily_challenge_answer"}
SLOW_TEXT_PENDING_ACTIONS = {"awaiting_reading_input", "awaiting_ai_tutor_question_number", "in_ai_tutor_conversation"}

CONTACT = "412101338@o365.tku.edu.tw"

DEACTIVATED_MESSAGE = (
    "您好，不好意思打擾了！\n\n"
    "本聊天機器人僅供參與研究的同學使用，這個帳號目前已停用，暫時無法繼續使用本服務。\n\n"
    f"如果您認為這是誤判，或有任何疑問，都歡迎聯繫我：{CONTACT}\n\n"
    "謝謝您之前的使用，也很抱歉造成不便！"
)

ACCESS_CODE_PROMPT = (
    "您好，歡迎使用日日くん！\n\n"
    "本帳號僅供參與研究的實驗組同學使用，請直接在聊天室輸入您的 6 碼開通碼完成開通。"
    "開通碼會寄送至您的學校信箱（o365.tku.edu.tw）。\n\n"
    "・一組開通碼僅能供一人開通，開通後即失效\n"
    "・開通碼限本人使用，請勿提供給他人\n"
    "・若經前測問卷比對，發現 LINE 名稱與開通的 LINE 帳號不符，經通知確認後將取消使用權限\n"
    "・如果沒有收到開通碼，或有更換 LINE 帳號等問題，請聯繫我\n\n"
    f"聯絡信箱：{CONTACT}"
)

ACCESS_CODE_INVALID = (
    "這組開通碼無效或已經被使用過了，請確認後再輸入一次（英文大小寫都可以）。\n\n"
    f"如果確定沒有打錯，請聯繫：{CONTACT}"
)

ACCESS_CODE_WELCOME = (
    "開通成功！現在可以開始使用囉，點選下方選單開始練習吧 🎉\n\n"
    "作答後的解說與 AI 助教回覆由 AI 生成，可能有誤，發現錯誤歡迎告訴我。\n\n"
    "下面是操作說明，之後忘記怎麼用可以回來看。"
)


def _notify_redeemed(line_user_id: str, code_row: dict) -> None:
    """有人兌換成功時寄信通知研究者，方便即時發現「某組碼被不該拿到的人用掉」這種狀況。
    只是輔助通知，查名字或寄信失敗都不該影響使用者已經開通的結果。"""
    try:
        display_name = line_client.get_display_name(line_user_id)
    except Exception:
        logger.exception("failed to fetch LINE display name for redeemed user")
        display_name = "（查詢顯示名稱失敗）"
    try:
        email_client.send_notification_email(
            subject=f"hibi_bot 開通碼已兌換：{code_row['code']}",
            body=(
                f"開通碼：{code_row['code']}（{code_row['category']}）\n"
                f"顯示名稱：{display_name}\n"
                f"line_user_id：{line_user_id}\n"
            ),
        )
    except Exception:
        logger.exception("failed to send redemption notification email")


def _show_loading_animation(line_user_id: str) -> None:
    try:
        line_client.show_loading_animation(line_user_id)
    except Exception:
        logger.exception("show_loading_animation failed for line_user_id=%s", line_user_id)


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

        if action in SLOW_POSTBACK_ACTIONS:
            _show_loading_animation(line_user_id)

        user_id, status = get_or_create_user(line_user_id)
        if status == "inactive":
            line_client.reply_text(reply_token, DEACTIVATED_MESSAGE)
            return
        if status == "pending":
            line_client.reply_text(reply_token, ACCESS_CODE_PROMPT)
            return
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

        user_id, status = get_or_create_user(line_user_id)
        if status == "inactive":
            line_client.reply_text(reply_token, DEACTIVATED_MESSAGE)
            return
        if status == "pending":
            # 還沒開通：看起來像開通碼（正規化後剛好 6 碼英數）才嘗試兌換；像「哈囉」這種一般
            # 聊天文字直接回開通說明，不然還沒拿到碼的人會莫名其妙收到「開通碼無效」
            if len(access_codes.normalize_code(text)) != access_codes.CODE_LENGTH:
                line_client.reply_text(reply_token, ACCESS_CODE_PROMPT)
                return
            code_row = access_codes.redeem(user_id, text)
            if code_row is None:
                line_client.reply_text(reply_token, ACCESS_CODE_INVALID)
                return
            # 前測時答到一半離開的同學，可能還留著舊的等待狀態（例如等待輸入讀音），開通當下
            # 清掉，不然開通後第一則文字會被當成舊題目的答案
            clear_session_state(user_id)
            # 加好友的歡迎訊息只在加入當下出現一次，前測就加過好友的同學看不到新版說明，
            # 所以開通成功時一律附上最新的操作說明圖
            if settings.guide_image_url:
                line_client.reply_text_and_image(reply_token, ACCESS_CODE_WELCOME, settings.guide_image_url)
            else:
                line_client.reply_text(reply_token, ACCESS_CODE_WELCOME)
            _notify_redeemed(line_user_id, code_row)
            return

        state = get_session_state(user_id)
        pending_action = state.get("pending_action") if state else None
        if pending_action in SLOW_TEXT_PENDING_ACTIONS:
            _show_loading_animation(line_user_id)

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
