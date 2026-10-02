"""諺語自 115 學年起改為單階段：答完選擇題直接給解說，不再要求輸入讀音。這裡驗證一般
練習、錯題複習兩條路都不會再進入讀音輸入，且作答明細有記下這次是意思題還是情境題。"""

from app.db.client import supabase
from app.services import feedback_generator, line_client, menu_actions

from .conftest import cleanup_test_data, insert_proverb_questions, make_exam_scope


def _patch_io(monkeypatch) -> list:
    sent: list = []
    monkeypatch.setattr(line_client, "reply_flex", lambda token, alt_text, contents: sent.append(alt_text))
    monkeypatch.setattr(line_client, "reply_text", lambda token, text: sent.append(text))
    monkeypatch.setattr(feedback_generator, "generate_feedback_text", lambda **kwargs: "（測試用解說）")
    return sent


def test_proverb_answer_goes_straight_to_feedback(test_user, monkeypatch):
    exam_scope = make_exam_scope("proverb1stage")
    groups = insert_proverb_questions(exam_scope, count=1)
    question_ids = [row["id"] for stages in groups.values() for row in stages.values()]
    situational = groups[1]["situational_choice"]
    semantic = groups[1]["semantic_choice"]
    sent = _patch_io(monkeypatch)

    try:
        # 情境題答錯 → 直接收到解說卡片，不是讀音輸入提示
        menu_actions.handle_answer(test_user, {"qid": situational["id"], "opt": "b"}, "token")
        assert sent == ["答題結果"]

        state = supabase.table("user_session_state").select("pending_action").eq("user_id", test_user).execute().data
        assert not state or state[0]["pending_action"] is None

        attempt = (
            supabase.table("attempts_log")
            .select("is_correct, answer_detail")
            .eq("user_id", test_user)
            .eq("question_id", situational["id"])
            .execute()
            .data[0]
        )
        assert attempt["is_correct"] is False
        assert attempt["answer_detail"] == {
            "stage1_variant": "situational_choice",
            "stage1_option": "b",
            "stage1_correct": False,
        }

        # 錯題複習答對 → 一樣直接解說，且錯題狀態變成 resolved
        sent.clear()
        menu_actions.handle_review_answer(test_user, {"qid": situational["id"], "opt": "a"}, "token")
        assert sent == ["複習結果"]
        wrong = (
            supabase.table("wrong_question_state")
            .select("status")
            .eq("user_id", test_user)
            .eq("question_id", situational["id"])
            .execute()
            .data[0]
        )
        assert wrong["status"] == "resolved"

        # 意思題也記得正確題型
        sent.clear()
        menu_actions.handle_answer(test_user, {"qid": semantic["id"], "opt": "a"}, "token")
        detail = (
            supabase.table("attempts_log")
            .select("answer_detail")
            .eq("user_id", test_user)
            .eq("question_id", semantic["id"])
            .execute()
            .data[0]["answer_detail"]
        )
        assert detail["stage1_variant"] == "semantic_choice" and detail["stage1_correct"] is True
    finally:
        supabase.table("feedback_logs").delete().in_(
            "attempt_log_id",
            [r["id"] for r in supabase.table("attempts_log").select("id").in_("question_id", question_ids).execute().data],
        ).execute()
        supabase.table("user_session_state").delete().eq("user_id", test_user).execute()
        cleanup_test_data(test_user, "proverb", exam_scope, question_ids)
