from typing import Any, Optional
from uuid import UUID

from app.db.client import supabase


def get_question(question_id: str) -> Optional[dict[str, Any]]:
    res = supabase.table("questions").select("*").eq("id", str(question_id)).execute()
    return res.data[0] if res.data else None


def get_proverb_stage2(stage1_question_id: str) -> Optional[dict[str, Any]]:
    res = supabase.table("questions").select("*").eq("parent_question_id", str(stage1_question_id)).execute()
    return res.data[0] if res.data else None


def find_question_by_number(mode: str, question_number: int) -> Optional[dict[str, Any]]:
    res = (
        supabase.table("questions")
        .select("*")
        .eq("mode", mode)
        .eq("question_number", question_number)
        .is_("parent_question_id", "null")
        .execute()
    )
    return res.data[0] if res.data else None


def option_text(question: dict[str, Any], option_id: Optional[str]) -> str:
    for option in question.get("options") or []:
        if option["id"] == option_id:
            return option["text"]
    return option_id or ""


def get_current_scope_and_round(user_id: str, mode: str) -> tuple[Optional[str], int]:
    """回傳 (exam_scope, current_round)。exam_scope 來自 active_exam_scope（由研究者/
    教師手動指定目前教學進度對應的範圍），若尚未設定則回傳 (None, 1)。current_round
    來自 scope_progress，若該使用者在這個範圍還沒有紀錄則預設為第 1 輪。
    """
    active = supabase.table("active_exam_scope").select("exam_scope").eq("mode", mode).execute().data
    if not active:
        return None, 1
    exam_scope = active[0]["exam_scope"]

    progress = (
        supabase.table("scope_progress")
        .select("current_round")
        .eq("user_id", str(user_id))
        .eq("mode", mode)
        .eq("exam_scope", exam_scope)
        .execute()
        .data
    )
    current_round = progress[0]["current_round"] if progress else 1
    return exam_scope, current_round


def get_available_questions_in_scope(
    user_id: str, mode: str, exam_scope: str, round_number: int
) -> list[dict[str, Any]]:
    """這個範圍在目前輪次還沒作答過的題目（依 question_number 排序）。"""
    scope_questions = (
        supabase.table("questions")
        .select("*")
        .eq("mode", mode)
        .eq("exam_scope", exam_scope)
        .is_("parent_question_id", "null")
        .order("question_number")
        .execute()
        .data
    )

    attempted_ids_this_round = {
        row["question_id"]
        for row in supabase.table("attempts_log")
        .select("question_id")
        .eq("user_id", str(user_id))
        .eq("round_number", round_number)
        .execute()
        .data
    }

    return [q for q in scope_questions if q["id"] not in attempted_ids_this_round]


def pick_next_question(user_id: UUID, mode: str) -> Optional[dict[str, Any]]:
    """挑下一題：目前範圍、目前輪次裡還沒作答過的題目（依 question_number 排序取
    第一個）。若這一輪已全部作答完（理論上此時應先重置），保底回傳範圍第一題，避免
    卡住無法互動。只考慮「頂層」題目（單語/言語知識的單一題目，或諺的第一階段），
    諺第二階段（parent_question_id 非 NULL）不算獨立一題。
    """
    exam_scope, current_round = get_current_scope_and_round(user_id, mode)
    if exam_scope is None:
        return None

    available = get_available_questions_in_scope(user_id, mode, exam_scope, current_round)
    if available:
        return available[0]

    all_questions = (
        supabase.table("questions")
        .select("*")
        .eq("mode", mode)
        .eq("exam_scope", exam_scope)
        .is_("parent_question_id", "null")
        .order("question_number")
        .execute()
        .data
    )
    return all_questions[0] if all_questions else None


def pick_wrong_question(user_id: UUID, mode: str) -> Optional[dict[str, Any]]:
    """從 wrong_question_state 挑一題這個模式底下、狀態仍是 wrong 的題目來複習。
    不限制在目前的 active_exam_scope，因為換範圍不代表舊範圍的錯題就不用複習了。
    """
    wrong_rows = (
        supabase.table("wrong_question_state")
        .select("question_id")
        .eq("user_id", str(user_id))
        .eq("status", "wrong")
        .execute()
        .data
    )
    if not wrong_rows:
        return None
    wrong_ids = {row["question_id"] for row in wrong_rows}

    questions = (
        supabase.table("questions")
        .select("*")
        .eq("mode", mode)
        .is_("parent_question_id", "null")
        .order("question_number")
        .execute()
        .data
    )
    for question in questions:
        if question["id"] in wrong_ids:
            return question
    return None
