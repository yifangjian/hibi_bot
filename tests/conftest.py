"""
共用測試 fixture／輔助函式：round_number 篩選回歸測試用。

安全原則：
- 每個測試都用獨一無二的 exam_scope（`pytest_<mode>_<random>`）跟全新的測試使用者，
  絕對不會碰到 active_exam_scope（真實正式環境目前教學進度指到的範圍），也不會跟任何
  真實學生的資料混在一起。
- 每個測試結束後（不管成功或失敗）都會清除自己建立的 questions／attempts_log／
  wrong_question_state／scope_progress／users 資料，不留殘骸。
"""

import uuid

import pytest

from app.db.client import supabase


@pytest.fixture
def test_user():
    """建立一個全新的測試使用者，測試結束後清除。"""
    line_user_id = f"pytest_{uuid.uuid4().hex[:16]}"
    row = supabase.table("users").insert({"line_user_id": line_user_id}).execute().data[0]
    user_id = row["id"]
    yield user_id
    supabase.table("users").delete().eq("id", user_id).execute()


def make_exam_scope(prefix: str) -> str:
    return f"pytest_{prefix}_{uuid.uuid4().hex[:8]}"


def insert_vocab_questions(exam_scope: str, count: int = 2) -> list[dict]:
    rows = []
    for i in range(1, count + 1):
        row = (
            supabase.table("questions")
            .insert(
                {
                    "mode": "vocab",
                    "exam_scope": exam_scope,
                    "question_number": i,
                    "stage": None,
                    "context_sentence": f"テスト単語{i}",
                    "blank_marker": None,
                    "options": [{"id": "a", "text": "正解"}, {"id": "b", "text": "誤答"}],
                    "correct_option": "a",
                    "explanation_rule": None,
                }
            )
            .execute()
            .data[0]
        )
        rows.append(row)
    return rows


def insert_language_knowledge_questions(exam_scope: str, count: int = 2) -> list[dict]:
    rows = []
    for i in range(1, count + 1):
        row = (
            supabase.table("questions")
            .insert(
                {
                    "mode": "language_knowledge",
                    "exam_scope": exam_scope,
                    "question_number": i,
                    "stage": None,
                    "context_sentence": f"テスト文法{i}＿＿。",
                    "blank_marker": "＿＿",
                    "options": [{"id": "a", "text": "正解"}, {"id": "b", "text": "誤答"}],
                    "correct_option": "a",
                    "explanation_rule": "テスト解析",
                }
            )
            .execute()
            .data[0]
        )
        rows.append(row)
    return rows


def insert_proverb_questions(exam_scope: str, count: int = 2) -> dict[int, dict[str, dict]]:
    """回傳 {question_number: {"semantic_choice": row, "situational_choice": row, "reading_input": row}}。"""
    groups: dict[int, dict[str, dict]] = {}
    for i in range(1, count + 1):
        semantic = (
            supabase.table("questions")
            .insert(
                {
                    "mode": "proverb",
                    "exam_scope": exam_scope,
                    "question_number": i,
                    "stage": "semantic_choice",
                    "context_sentence": f"テスト諺{i}の意味は？",
                    "blank_marker": None,
                    "options": [{"id": "a", "text": "正解の意味"}, {"id": "b", "text": "誤答の意味"}],
                    "correct_option": "a",
                    "explanation_rule": f"【諺語】テスト諺{i}",
                }
            )
            .execute()
            .data[0]
        )
        situational = (
            supabase.table("questions")
            .insert(
                {
                    "mode": "proverb",
                    "exam_scope": exam_scope,
                    "question_number": i,
                    "stage": "situational_choice",
                    "context_sentence": f"状況＿＿テスト諺{i}",
                    "blank_marker": "＿＿",
                    "options": [{"id": "a", "text": f"テスト諺{i}"}, {"id": "b", "text": "別の諺"}],
                    "correct_option": "a",
                    "explanation_rule": f"【諺語】テスト諺{i}",
                }
            )
            .execute()
            .data[0]
        )
        reading = (
            supabase.table("questions")
            .insert(
                {
                    "mode": "proverb",
                    "exam_scope": exam_scope,
                    "question_number": i,
                    "stage": "reading_input",
                    "context_sentence": None,
                    "blank_marker": None,
                    "options": None,
                    "correct_option": f"てすとことわざ{i}",
                    "explanation_rule": None,
                }
            )
            .execute()
            .data[0]
        )
        groups[i] = {"semantic_choice": semantic, "situational_choice": situational, "reading_input": reading}
    return groups


def cleanup_test_data(user_id: str, mode: str, exam_scope: str, question_ids: list[str]) -> None:
    """清除測試建立的資料。question_ids 只會是這個測試自己建立的題目 id，不會誤刪其他資料；
    questions 依 (mode, exam_scope) 清除，因為這個 exam_scope 是這次測試獨有的隨機字串。
    """
    if question_ids:
        supabase.table("attempts_log").delete().in_("question_id", question_ids).execute()
        supabase.table("wrong_question_state").delete().in_("question_id", question_ids).execute()
    supabase.table("scope_progress").delete().eq("user_id", user_id).eq("mode", mode).eq(
        "exam_scope", exam_scope
    ).execute()
    supabase.table("questions").delete().eq("mode", mode).eq("exam_scope", exam_scope).execute()
