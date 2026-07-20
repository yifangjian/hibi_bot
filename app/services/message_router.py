import re
import threading
from uuid import UUID

from app.services import ai_tutor, daily_challenge, feedback_generator, flex_templates, line_client
from app.services.answer_handler import finalize_attempt
from app.services.question_picker import get_proverb_stage2, get_question, is_correct_option, option_text
from app.services.session_state import clear_session_state, get_session_state

QUESTION_NUMBER_RE = re.compile(r"^\d+$")


def handle_text_message(user_id: UUID, text: str, reply_token: str) -> None:
    state = get_session_state(user_id)
    pending_action = state.get("pending_action") if state else None

    if pending_action == "awaiting_reading_input":
        _handle_reading_input(user_id, text, reply_token, state.get("context") or {})
    elif pending_action == "awaiting_ai_tutor_question_number":
        _handle_ai_tutor_question_number(user_id, text, reply_token, state.get("context") or {})
    elif pending_action == "in_ai_tutor_conversation":
        ai_tutor.continue_conversation(user_id, state.get("context") or {}, text, reply_token)
    # 不在這幾種等待狀態下收到的文字訊息，維持現有預設行為（不處理）


def _handle_reading_input(user_id: UUID, text: str, reply_token: str, context: dict) -> None:
    stage1_question_id = context["question_id"]
    mode = context["mode"]
    stage1_option = context["stage1_option"]
    stage1_correct = context["stage1_correct"]
    challenge_id = context.get("challenge_id")
    attempt_type = context.get("attempt_type", "first")

    stage1_question = get_question(stage1_question_id)
    stage2_question = get_proverb_stage2(stage1_question)

    stage2_correct = bool(stage2_question) and is_correct_option(stage2_question, text.strip())
    is_correct = stage1_correct and stage2_correct

    # AI 生成回饋（chat_completion）通常比 finalize_attempt 整段 DB 寫入還慢，而且它不需要
    # attempt["id"]（只有最後寫 feedback_logs 才需要），所以提前在背景執行緒起跑，跟
    # finalize_attempt 平行處理，減少使用者實際等待的總時間。一般練習跟每日挑戰都需要
    # 顯示解析，共用同一套邏輯。
    explanation_parts = []
    if stage1_question and stage1_question.get("explanation_rule"):
        explanation_parts.append(f"【第一階段】{stage1_question['explanation_rule']}")
    if stage2_question and stage2_question.get("explanation_rule"):
        explanation_parts.append(f"【讀音】{stage2_question['explanation_rule']}")
    explanation_text = "\n".join(explanation_parts)

    stage1_selected_text = option_text(stage1_question, stage1_option)
    stage1_correct_text = option_text(stage1_question, stage1_question.get("correct_option"))
    stage2_correct_reading = stage2_question.get("correct_option") if stage2_question else ""

    feedback_result: dict = {}

    def _run_feedback_generation() -> None:
        feedback_result["text"] = feedback_generator.generate_feedback_text(
            context_sentence=stage1_question.get("context_sentence") or "",
            correct_option_text=f"選項：{stage1_correct_text}；讀音：{stage2_correct_reading}",
            selected_option_text=f"選項：{stage1_selected_text}；讀音：{text}",
            explanation_rule=explanation_text,
            is_correct=is_correct,
        )

    feedback_thread = threading.Thread(target=_run_feedback_generation)
    feedback_thread.start()

    attempt = finalize_attempt(
        user_id=user_id,
        question=stage1_question,
        is_correct=is_correct,
        selected_option=stage1_option,
        answer_detail={
            "stage1_variant": stage1_question.get("stage") if stage1_question else None,
            "stage1_option": stage1_option,
            "stage1_correct": stage1_correct,
            "stage2_reading_input": text,
            "stage2_correct": stage2_correct,
        },
        daily_challenge_id=challenge_id,
        attempt_type=attempt_type,
    )
    clear_session_state(user_id)

    feedback_thread.join()
    feedback_text = feedback_result["text"]
    feedback_generator.log_feedback(attempt["id"], feedback_text)

    example_sentence = feedback_generator.extract_example_sentence(stage1_question.get("explanation_rule"))

    if challenge_id:
        # 每日挑戰的一題：先推進挑戰進度（不等使用者按下一題），再顯示解析回饋卡片，
        # 卡片上的「下一題」按鈕會走 daily_challenge_continue，由使用者主動推進。
        daily_challenge.advance_challenge(challenge_id, stage1_question["id"], is_correct)
        retry_action = "daily_challenge_continue"
    else:
        retry_action = "review_wrong" if attempt_type == "review" else "next_question"

    line_client.reply_flex(
        reply_token,
        alt_text="答題結果",
        contents=flex_templates.build_feedback_card(
            is_correct,
            feedback_text,
            mode,
            retry_action=retry_action,
            example_sentence=example_sentence,
            challenge_id=challenge_id,
        ),
    )


def _handle_ai_tutor_question_number(user_id: UUID, text: str, reply_token: str, context: dict) -> None:
    stripped = text.strip()
    if not QUESTION_NUMBER_RE.match(stripped):
        line_client.reply_text(reply_token, "請輸入有效的題號（純數字）")
        return

    ai_tutor.start_conversation(user_id, context.get("mode"), stripped, reply_token)
