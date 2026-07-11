"""
回歸測試：查詢使用者作答狀況時，round_number（目前輪次）有沒有正確篩選。

背景：這類 bug 已經出現兩次——Phase 5 的 update_unit_progress、Phase 7 的
pick_next_question——都是「查詢時忘記把目前輪次考慮進去」，導致重置後舊輪次的作答
紀錄被誤判成「這輪已經答過」。這份測試涵蓋三個模式（単語／諺／言語知識）各自的完整
情境：round 1 作答 → 重置 → round 2 應該視為全部未作答，且 round 1 的歷史紀錄完整保留。

盤點結論（詳見隨附的技術報告）：目前程式碼裡實際會查詢 attempts_log 的地方只有
`get_available_questions_in_scope`／`count_attempted_in_scope` 兩處，兩者都已經正確
帶入 round_number 篩選；`wrong_question_state` 相關的查詢（`count_wrong_in_scope`／
`pick_wrong_question`）設計上不需要 round 篩選，因為那是一個「目前狀態」表（PK 是
user_id+question_id，不是逐輪次累積的歷史紀錄），而且重置的前提本身就要求
all_wrong_resolved 為 true，保證進入新輪次時不會有殘留的 wrong 狀態。這裡沒有發現
第三個 bug 實例，這份測試的目的是把「目前是正確的」這件事釘住，避免以後不小心改壞。
"""

from uuid import UUID

import app.services.line_client as line_client
import app.services.reset_handler as reset_handler
from app.db.client import supabase
from app.services.answer_handler import finalize_attempt
from app.services.progress import count_attempted_in_scope, question_number_map
from app.services.question_picker import get_available_questions_in_scope, get_scope_progress_index
from app.services.reset_handler import handle_reset_unit

from .conftest import (
    cleanup_test_data,
    insert_language_knowledge_questions,
    insert_proverb_questions,
    insert_vocab_questions,
    make_exam_scope,
)


def _trigger_reset_and_capture(monkeypatch, user_id: UUID, mode: str, exam_scope: str) -> list[str]:
    """呼叫真正的 handle_reset_unit（走真實的條件判斷路徑，不是直接改 DB 模擬），
    攔截 reply_text 送出的訊息方便斷言。

    handle_reset_unit 內部會呼叫 get_current_scope_and_round(user_id, mode) 來決定要檢查
    哪個 exam_scope——這個函式讀的是 active_exam_scope 表（正式環境目前教學進度指到的
    範圍），不是我們測試用的隨機 exam_scope。這裡把它 monkeypatch 掉，讓 handle_reset_unit
    檢查我們測試用的 exam_scope，同時完全不去碰真正的 active_exam_scope（那是正式環境正在
    使用中的共用設定，測試不該動它）。
    """
    messages: list[str] = []
    monkeypatch.setattr(line_client, "reply_text", lambda token, text: messages.append(text))
    monkeypatch.setattr(reset_handler, "get_current_scope_and_round", lambda uid, mode: (exam_scope, 1))
    handle_reset_unit(user_id, {"mode": mode}, "dummy_token")
    return messages


def test_round_filtering_vocab(test_user, monkeypatch):
    exam_scope = make_exam_scope("vocab")
    q1, q2 = insert_vocab_questions(exam_scope, count=2)
    question_ids = [q1["id"], q2["id"]]

    try:
        # Round 1：Q1 直接答對；Q2 先答錯，再透過複習答對（resolve wrong）。
        finalize_attempt(user_id=test_user, question=q1, is_correct=True, selected_option="a")
        finalize_attempt(user_id=test_user, question=q2, is_correct=False, selected_option="b")
        finalize_attempt(
            user_id=test_user, question=q2, is_correct=True, selected_option="a", attempt_type="review"
        )

        index = get_scope_progress_index("vocab", exam_scope)
        id_to_number = question_number_map(index)

        assert count_attempted_in_scope(test_user, id_to_number, round_number=1) == 2

        messages = _trigger_reset_and_capture(monkeypatch, test_user, "vocab", exam_scope)
        assert messages, "reset_handler 沒有送出任何回覆"
        assert "已重置" in messages[-1], f"預期重置成功，實際收到：{messages}"

        # Round 2：應該視為兩題都還沒作答過。
        assert count_attempted_in_scope(test_user, id_to_number, round_number=2) == 0

        available_round2 = get_available_questions_in_scope(test_user, "vocab", exam_scope, round_number=2)
        assert {q["question_number"] for q in available_round2} == {1, 2}, (
            "重置後 round 2 應該兩題都重新出現，卻有題目被誤判成已作答過"
        )

        # Round 1 的歷史紀錄要完整保留：Q1 正確 1 筆、Q2 錯誤 1 筆、Q2 複習正確 1 筆。
        old_attempts = (
            supabase.table("attempts_log")
            .select("id, round_number, is_correct")
            .in_("question_id", question_ids)
            .eq("round_number", 1)
            .execute()
            .data
        )
        assert len(old_attempts) == 3, f"round=1 應有 3 筆歷史紀錄，實際 {len(old_attempts)} 筆"
    finally:
        cleanup_test_data(test_user, "vocab", exam_scope, question_ids)


def test_round_filtering_language_knowledge(test_user, monkeypatch):
    exam_scope = make_exam_scope("lk")
    q1, q2 = insert_language_knowledge_questions(exam_scope, count=2)
    question_ids = [q1["id"], q2["id"]]

    try:
        finalize_attempt(user_id=test_user, question=q1, is_correct=True, selected_option="a")
        finalize_attempt(user_id=test_user, question=q2, is_correct=False, selected_option="b")
        finalize_attempt(
            user_id=test_user, question=q2, is_correct=True, selected_option="a", attempt_type="review"
        )

        index = get_scope_progress_index("language_knowledge", exam_scope)
        id_to_number = question_number_map(index)
        assert count_attempted_in_scope(test_user, id_to_number, round_number=1) == 2

        messages = _trigger_reset_and_capture(monkeypatch, test_user, "language_knowledge", exam_scope)
        assert messages and "已重置" in messages[-1], f"預期重置成功，實際收到：{messages}"

        assert count_attempted_in_scope(test_user, id_to_number, round_number=2) == 0

        available_round2 = get_available_questions_in_scope(
            test_user, "language_knowledge", exam_scope, round_number=2
        )
        assert {q["question_number"] for q in available_round2} == {1, 2}

        old_attempts = (
            supabase.table("attempts_log")
            .select("id")
            .in_("question_id", question_ids)
            .eq("round_number", 1)
            .execute()
            .data
        )
        assert len(old_attempts) == 3
    finally:
        cleanup_test_data(test_user, "language_knowledge", exam_scope, question_ids)


def test_round_filtering_proverb(test_user, monkeypatch):
    exam_scope = make_exam_scope("proverb")
    groups = insert_proverb_questions(exam_scope, count=2)
    question_ids = [row["id"] for stages in groups.values() for row in stages.values()]

    # 諺語的 finalize_attempt 是用「第一階段代表列」當 question——這裡直接指定用哪個變體，
    # 不是走隨機挑選（隨機挑選本身已經在 Phase 7 其他測試驗證過，這裡要驗證的是輪次篩選）。
    q1_stage1 = groups[1]["semantic_choice"]
    q2_stage1 = groups[2]["situational_choice"]

    try:
        finalize_attempt(user_id=test_user, question=q1_stage1, is_correct=True, selected_option="a")
        finalize_attempt(user_id=test_user, question=q2_stage1, is_correct=False, selected_option="b")
        finalize_attempt(
            user_id=test_user, question=q2_stage1, is_correct=True, selected_option="a", attempt_type="review"
        )

        index = get_scope_progress_index("proverb", exam_scope)
        id_to_number = question_number_map(index)
        assert count_attempted_in_scope(test_user, id_to_number, round_number=1) == 2

        messages = _trigger_reset_and_capture(monkeypatch, test_user, "proverb", exam_scope)
        assert messages and "已重置" in messages[-1], f"預期重置成功，實際收到：{messages}"

        assert count_attempted_in_scope(test_user, id_to_number, round_number=2) == 0

        available_round2 = get_available_questions_in_scope(test_user, "proverb", exam_scope, round_number=2)
        assert {q["question_number"] for q in available_round2} == {1, 2}, (
            "重置後 round 2 兩句諺語都應該重新出現"
        )

        # 額外驗證（諺語特有）：round 2 的候選池要涵蓋兩種變體，不會因為 round 1 用過
        # 哪個變體就被限制住——多次呼叫應該兩種 stage 都抽得到。
        picked_stages = set()
        for _ in range(20):
            available = get_available_questions_in_scope(test_user, "proverb", exam_scope, round_number=2)
            q1_representative = next(q for q in available if q["question_number"] == 1)
            picked_stages.add(q1_representative["stage"])
        assert picked_stages == {"semantic_choice", "situational_choice"}, (
            f"round 2 的候選池應該兩種變體都能抽到，實際只抽到：{picked_stages}"
        )

        old_attempts = (
            supabase.table("attempts_log")
            .select("id")
            .in_("question_id", question_ids)
            .eq("round_number", 1)
            .execute()
            .data
        )
        assert len(old_attempts) == 3
    finally:
        cleanup_test_data(test_user, "proverb", exam_scope, question_ids)
