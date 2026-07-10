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


def pick_next_question(user_id: UUID, mode: str) -> Optional[dict[str, Any]]:
    """挑下一題：優先給該使用者在此模式下還沒作答過的題目（依單元順序），
    若全部都答過則從頭重來。只考慮「頂層」題目（單語/言語知識的單一題目，
    或諺的第一階段），諺第二階段（parent_question_id 非 NULL）不算獨立一題。
    """
    attempted = supabase.table("attempts_log").select("question_id").eq("user_id", str(user_id)).execute()
    attempted_ids = {row["question_id"] for row in attempted.data}

    all_questions = (
        supabase.table("questions")
        .select("*")
        .eq("mode", mode)
        .is_("parent_question_id", "null")
        .order("unit_number")
        .execute()
        .data
    )
    if not all_questions:
        return None

    unattempted = [q for q in all_questions if q["id"] not in attempted_ids]
    return unattempted[0] if unattempted else all_questions[0]
