import logging
from typing import Optional
from uuid import UUID

from app.services import daily_challenge, feedback_generator, flex_templates, line_client
from app.services.answer_handler import finalize_attempt
from app.services.question_picker import get_question, option_text, pick_next_question
from app.services.session_state import clear_session_state, set_session_state

logger = logging.getLogger("hibi_bot.menu_actions")


def _serve_next_question(user_id: UUID, mode: Optional[str], reply_token: str) -> None:
    question = pick_next_question(user_id, mode)
    if not question:
        line_client.reply_text(reply_token, f"「{mode}」目前還沒有題目，請聯繫老師新增題庫內容。")
        return
    line_client.reply_flex(reply_token, alt_text="練習題", contents=flex_templates.build_question_card(question))


def handle_enter_mode(user_id: UUID, params: dict, reply_token: str) -> None:
    logger.info("Stub handle_enter_mode: user=%s params=%s", user_id, params)


def handle_view_progress(user_id: UUID, params: dict, reply_token: str) -> None:
    logger.info("Stub handle_view_progress: user=%s params=%s", user_id, params)


def handle_start_practice(user_id: UUID, params: dict, reply_token: str) -> None:
    _serve_next_question(user_id, params.get("mode"), reply_token)


def handle_next_question(user_id: UUID, params: dict, reply_token: str) -> None:
    clear_session_state(user_id)
    _serve_next_question(user_id, params.get("mode"), reply_token)


def handle_enter_wrong_mode(user_id: UUID, params: dict, reply_token: str) -> None:
    logger.info("Stub handle_enter_wrong_mode: user=%s params=%s", user_id, params)


def handle_reset_unit(user_id: UUID, params: dict, reply_token: str) -> None:
    logger.info("Stub handle_reset_unit: user=%s params=%s", user_id, params)


def handle_back(user_id: UUID, params: dict, reply_token: str) -> None:
    clear_session_state(user_id)
    logger.info("handle_back: cleared session state, user=%s params=%s", user_id, params)


def handle_ai_tutor_prompt(user_id: UUID, params: dict, reply_token: str) -> None:
    set_session_state(user_id, "awaiting_ai_tutor_question_number", {"mode": params.get("mode")})
    line_client.reply_text(reply_token, "請輸入你想詢問的題號")


def handle_review_wrong(user_id: UUID, params: dict, reply_token: str) -> None:
    logger.info("Stub handle_review_wrong: user=%s params=%s", user_id, params)


def handle_answer(user_id: UUID, params: dict, reply_token: str) -> None:
    qid = params.get("qid")
    opt = params.get("opt")
    question = get_question(qid)
    if not question:
        line_client.reply_text(reply_token, "找不到這一題，請重新開始練習。")
        return

    is_correct = opt == question.get("correct_option")

    if question["mode"] == "proverb" and question.get("stage") in ("semantic_choice", "situational_choice"):
        # 諺第一階段：先記錄選擇，轉入讀音輸入階段，尚未寫入 attempts_log
        set_session_state(
            user_id,
            "awaiting_reading_input",
            {
                "question_id": question["id"],
                "mode": "proverb",
                "stage1_option": opt,
                "stage1_correct": is_correct,
            },
        )
        line_client.reply_flex(
            reply_token,
            alt_text="請輸入讀音",
            contents=flex_templates.build_reading_input_prompt_card(question),
        )
        return

    # 単語 / 言語知識：單階段，直接判定並寫入
    attempt = finalize_attempt(user_id=user_id, question=question, is_correct=is_correct, selected_option=opt)
    feedback_text = feedback_generator.generate_and_log_feedback(
        attempt_log_id=attempt["id"],
        context_sentence=question.get("context_sentence") or "",
        correct_option_text=option_text(question, question.get("correct_option")),
        selected_option_text=option_text(question, opt),
        explanation_rule=question.get("explanation_rule") or "",
        is_correct=is_correct,
    )
    line_client.reply_flex(
        reply_token,
        alt_text="答題結果",
        contents=flex_templates.build_feedback_card(is_correct, feedback_text, question["mode"]),
    )


def handle_daily_challenge_start(user_id: UUID, params: dict, reply_token: str) -> None:
    daily_challenge.start_or_resume(user_id, params.get("challenge_id"), reply_token)


def handle_daily_challenge_answer(user_id: UUID, params: dict, reply_token: str) -> None:
    daily_challenge.handle_challenge_answer(user_id, params, reply_token)


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
    "daily_challenge_start": handle_daily_challenge_start,
    "daily_challenge_answer": handle_daily_challenge_answer,
}


def dispatch(action: Optional[str], params: dict, user_id: UUID, reply_token: str) -> None:
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        logger.warning("No handler registered for action=%s params=%s", action, params)
        return
    handler(user_id, params, reply_token)
