"""AI 助教使用紀錄：每次輸入題號開一個新的 conversation_id，追問沿用；題號查不到、額度用完
被擋下也要留紀錄（kind 區分），供分析「有沒有用、用了幾次、想用卻沒用成」。"""

from app.config import settings
from app.db.client import supabase
from app.services import ai_tutor, line_client, message_router
from app.services.session_state import get_session_state

from .conftest import cleanup_test_data, insert_language_knowledge_questions, make_exam_scope


def _logs(user_id: str) -> list[dict]:
    return (
        supabase.table("ai_conversation_log")
        .select("role, message, kind, conversation_id, question_id")
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
        .data
    )


def test_ai_tutor_usage_is_logged_by_conversation(test_user, monkeypatch):
    exam_scope = make_exam_scope("aitutor")
    questions = insert_language_knowledge_questions(exam_scope, count=1)
    monkeypatch.setattr(ai_tutor, "get_current_scope_and_round", lambda user_id, mode: (exam_scope, 1))
    monkeypatch.setattr(ai_tutor, "chat_completion", lambda messages: "（測試用回覆）")
    monkeypatch.setattr(line_client, "reply_flex", lambda token, alt_text, contents: None)
    monkeypatch.setattr(line_client, "reply_text", lambda token, text: None)
    monkeypatch.setattr(settings, "ai_tutor_daily_turn_limit", 1)

    def ask_number(text: str) -> None:
        message_router._handle_ai_tutor_question_number(test_user, text, "token", {"mode": "language_knowledge"})

    def follow_up(text: str) -> None:
        context = get_session_state(test_user)["context"]
        ai_tutor.continue_conversation(test_user, context, text, "token")

    try:
        ask_number("第一題")  # 不是數字
        ask_number("99")  # 查不到
        ask_number("1")
        follow_up("為什麼？")
        follow_up("還有呢？")  # 超過每日 1 次追問
        ask_number("1")  # 同一題再開一次對話

        logs = _logs(test_user)
        assert [(r["role"], r["kind"]) for r in logs] == [
            ("user", "lookup_failed"),
            ("user", "lookup_failed"),
            ("user", "initial"),
            ("assistant", "initial"),
            ("user", "followup"),
            ("assistant", "followup"),
            ("user", "limit_reached"),
            ("user", "initial"),
            ("assistant", "initial"),
        ]
        assert [r["message"] for r in logs[:2]] == ["第一題", "99"]
        assert logs[0]["question_id"] is None and logs[0]["conversation_id"] is None

        first = logs[2]["conversation_id"]
        assert first and all(r["conversation_id"] == first for r in logs[2:7])
        assert logs[7]["conversation_id"] == logs[8]["conversation_id"] != first
    finally:
        supabase.table("ai_conversation_log").delete().eq("user_id", test_user).execute()
        supabase.table("ai_conversation_usage").delete().eq("user_id", test_user).execute()
        supabase.table("user_session_state").delete().eq("user_id", test_user).execute()
        cleanup_test_data(test_user, "language_knowledge", exam_scope, [q["id"] for q in questions])
