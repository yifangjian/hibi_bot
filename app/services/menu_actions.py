import logging
from typing import Optional
from uuid import UUID

from app.db.client import supabase
from app.services import daily_challenge, feedback_generator, flex_templates, line_client, progress_view, reset_handler
from app.services.answer_handler import finalize_attempt, proverb_answer_detail
from app.services.question_picker import get_question, is_correct_option, pick_next_question, pick_wrong_question
from app.services.rich_menu_alias import mode_alias
from app.services.session_state import clear_session_state, set_session_state

logger = logging.getLogger("hibi_bot.menu_actions")


def _switch_menu(user_id: UUID, alias_id: str) -> None:
    """從卡片上的按鈕（「再練一題」「繼續練習」「繼續複習」）出題時，把圖文選單切回對應的
    子選單。按圖文選單本身的按鈕時 LINE 會自己切換，但卡片按鈕只會送 postback，選單會停在
    使用者最後停留的地方——例如練習中按了「返回」再點「再練一題」，選單就卡在模式選單，
    看不到「AI助教」。在回覆送出之後才呼叫，不拖慢使用者看到題目的時間；切換失敗只記錄，
    不影響已經送出的題目。"""
    try:
        rows = supabase.table("users").select("line_user_id").eq("id", str(user_id)).execute().data
        if rows:
            line_client.switch_rich_menu(rows[0]["line_user_id"], alias_id)
    except Exception:
        logger.exception("failed to switch rich menu to %s for user=%s", alias_id, user_id)


def _serve_next_question(user_id: UUID, mode: Optional[str], reply_token: str) -> None:
    question = pick_next_question(user_id, mode)
    if not question:
        label = flex_templates.MODE_LABELS.get(mode, mode)
        line_client.reply_text(reply_token, f"「{label}」目前還沒有題目，請聯繫老師新增題庫內容。")
        return
    line_client.reply_flex(reply_token, alt_text="練習題", contents=flex_templates.build_question_card(question))


def handle_enter_mode(user_id: UUID, params: dict, reply_token: str) -> None:
    logger.info("Stub handle_enter_mode: user=%s params=%s", user_id, params)


def handle_view_progress(user_id: UUID, params: dict, reply_token: str) -> None:
    progress_view.show_progress(user_id, reply_token)


def handle_start_practice(user_id: UUID, params: dict, reply_token: str) -> None:
    _serve_next_question(user_id, params.get("mode"), reply_token)


def handle_next_question(user_id: UUID, params: dict, reply_token: str) -> None:
    clear_session_state(user_id)
    mode = params.get("mode")
    _serve_next_question(user_id, mode, reply_token)
    if mode in flex_templates.MODE_LABELS:
        _switch_menu(user_id, mode_alias("start_practice", mode))


def handle_enter_wrong_mode(user_id: UUID, params: dict, reply_token: str) -> None:
    logger.info("Stub handle_enter_wrong_mode: user=%s params=%s", user_id, params)


def handle_reset_unit(user_id: UUID, params: dict, reply_token: str) -> None:
    reset_handler.handle_reset_unit(user_id, params, reply_token)


def handle_back(user_id: UUID, params: dict, reply_token: str) -> None:
    clear_session_state(user_id)
    logger.info("handle_back: cleared session state, user=%s params=%s", user_id, params)


def handle_ai_tutor_prompt(user_id: UUID, params: dict, reply_token: str) -> None:
    set_session_state(user_id, "awaiting_ai_tutor_question_number", {"mode": params.get("mode")})
    line_client.reply_text(reply_token, "請輸入你想詢問的題號")


def handle_review_wrong(user_id: UUID, params: dict, reply_token: str) -> None:
    mode = params.get("mode")
    question = pick_wrong_question(user_id, mode)
    if not question:
        label = flex_templates.MODE_LABELS.get(mode, mode)
        line_client.reply_text(reply_token, f"「{label}」目前沒有待複習的錯題囉！")
        return
    line_client.reply_flex(
        reply_token,
        alt_text="複習錯題",
        contents=flex_templates.build_question_card(question, action="review_answer"),
    )
    _switch_menu(user_id, mode_alias("wrong_question", mode))


def handle_review_answer(user_id: UUID, params: dict, reply_token: str) -> None:
    qid = params.get("qid")
    opt = params.get("opt")
    question = get_question(qid)
    if not question:
        line_client.reply_text(reply_token, "找不到這一題，請重新進入錯題模式。")
        return

    mode = question["mode"]
    is_correct = is_correct_option(question, opt)

    # 三種模式都是單階段：直接判定並寫入（attempt_type=review，答對會把這題從 wrong 標記為 resolved）
    feedback_thread, feedback_result = feedback_generator.start_feedback_generation(question, opt, is_correct)
    attempt = finalize_attempt(
        user_id=user_id,
        question=question,
        is_correct=is_correct,
        selected_option=opt,
        answer_detail=proverb_answer_detail(question, opt, is_correct),
        attempt_type="review",
    )
    feedback_text, example_sentence = feedback_generator.finish_feedback_text(question, attempt["id"], feedback_thread, feedback_result)
    line_client.reply_flex(
        reply_token,
        alt_text="複習結果",
        contents=flex_templates.build_feedback_card(
            is_correct,
            feedback_text,
            mode,
            retry_action="review_wrong",
            example_sentence=example_sentence,
            ai_generated=not feedback_generator.has_no_explanation(question),
        ),
    )


def handle_answer(user_id: UUID, params: dict, reply_token: str) -> None:
    qid = params.get("qid")
    opt = params.get("opt")
    question = get_question(qid)
    if not question:
        line_client.reply_text(reply_token, "找不到這一題，請重新開始練習。")
        return

    is_correct = is_correct_option(question, opt)

    # 三種模式都是單階段：直接判定並寫入
    feedback_thread, feedback_result = feedback_generator.start_feedback_generation(question, opt, is_correct)
    attempt = finalize_attempt(
        user_id=user_id,
        question=question,
        is_correct=is_correct,
        selected_option=opt,
        answer_detail=proverb_answer_detail(question, opt, is_correct),
    )
    feedback_text, example_sentence = feedback_generator.finish_feedback_text(question, attempt["id"], feedback_thread, feedback_result)
    line_client.reply_flex(
        reply_token,
        alt_text="答題結果",
        contents=flex_templates.build_feedback_card(
            is_correct,
            feedback_text,
            question["mode"],
            example_sentence=example_sentence,
            ai_generated=not feedback_generator.has_no_explanation(question),
        ),
    )


def handle_daily_challenge_start(user_id: UUID, params: dict, reply_token: str) -> None:
    daily_challenge.start_or_resume(user_id, params.get("challenge_id"), reply_token)


def handle_daily_challenge_answer(user_id: UUID, params: dict, reply_token: str) -> None:
    daily_challenge.handle_challenge_answer(user_id, params, reply_token)


def handle_daily_challenge_continue(user_id: UUID, params: dict, reply_token: str) -> None:
    daily_challenge.handle_challenge_continue(user_id, params.get("challenge_id"), reply_token)


ACTION_HANDLERS = {
    "enter_mode": handle_enter_mode,
    "view_progress": handle_view_progress,
    "start_practice": handle_start_practice,
    "next_question": handle_next_question,
    "enter_wrong_mode": handle_enter_wrong_mode,
    "reset_unit": handle_reset_unit,
    "back": handle_back,
    "ai_tutor_prompt": handle_ai_tutor_prompt,
    "review_wrong": handle_review_wrong,
    "answer": handle_answer,
    "review_answer": handle_review_answer,
    "daily_challenge_start": handle_daily_challenge_start,
    "daily_challenge_answer": handle_daily_challenge_answer,
    "daily_challenge_continue": handle_daily_challenge_continue,
}


def dispatch(action: Optional[str], params: dict, user_id: UUID, reply_token: str) -> None:
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        logger.warning("No handler registered for action=%s params=%s", action, params)
        return
    # 每個 postback 都先清掉舊的等待狀態（awaiting_reading_input 等）再進 handler，避免
    # 使用者中途放棄某個流程（例如諺答完第一階段、還沒打讀音就跳去別的選單）之後，殘留的
    # 舊狀態把使用者之後隨手打的文字誤判成是在回答那個已經放棄的題目。真的需要進入等待
    # 狀態的 handler（例如 answer 判斷是諺第一階段、ai_tutor_prompt）會在自己的邏輯裡重新
    # set_session_state，不受這裡影響。
    clear_session_state(user_id)
    handler(user_id, params, reply_token)
