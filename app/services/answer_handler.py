from typing import Any, Optional
from uuid import UUID

from app.db.client import supabase
from app.services.progress import update_scope_progress


def _get_challenge_pushed_at(daily_challenge_id: Optional[str]) -> Optional[str]:
    """若這次作答屬於每日挑戰，回傳該挑戰被推播的時間；否則（使用者自發練習）回傳 None。"""
    if not daily_challenge_id:
        return None
    rows = (
        supabase.table("push_log")
        .select("pushed_at")
        .eq("challenge_id", str(daily_challenge_id))
        .order("pushed_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0]["pushed_at"] if rows else None


def _get_current_round(user_id: UUID, mode: str, exam_scope: str) -> int:
    rows = (
        supabase.table("scope_progress")
        .select("current_round")
        .eq("user_id", str(user_id))
        .eq("mode", mode)
        .eq("exam_scope", exam_scope)
        .execute()
        .data
    )
    return rows[0]["current_round"] if rows else 1


def finalize_attempt(
    user_id: UUID,
    question: dict[str, Any],
    is_correct: bool,
    selected_option: Optional[str],
    answer_detail: Optional[dict[str, Any]] = None,
    attempt_type: str = "first",
    daily_challenge_id: Optional[str] = None,
) -> dict[str, Any]:
    """寫入一筆 attempts_log，更新 wrong_question_state 與 scope_progress。

    question 為該題的「代表列」：単語/言語知識為題目本身，諺則為第一階段列
    （整題的識別以第一階段的 id 為準）。daily_challenge_id 有值代表這是每日挑戰的一題。
    """
    pushed_at = _get_challenge_pushed_at(daily_challenge_id)
    round_number = _get_current_round(user_id, question["mode"], question["exam_scope"])

    inserted = (
        supabase.table("attempts_log")
        .insert(
            {
                "user_id": str(user_id),
                "question_id": question["id"],
                "selected_option": selected_option,
                "is_correct": is_correct,
                "attempt_type": attempt_type,
                "answer_detail": answer_detail,
                "pushed_at": pushed_at,
                "round_number": round_number,
                "daily_challenge_id": str(daily_challenge_id) if daily_challenge_id else None,
            }
        )
        .execute()
    )

    if not is_correct:
        supabase.table("wrong_question_state").upsert(
            {"user_id": str(user_id), "question_id": question["id"], "status": "wrong"}
        ).execute()
    else:
        existing = (
            supabase.table("wrong_question_state")
            .select("status")
            .eq("user_id", str(user_id))
            .eq("question_id", question["id"])
            .execute()
        )
        if existing.data and existing.data[0]["status"] == "wrong":
            supabase.table("wrong_question_state").update({"status": "resolved"}).eq(
                "user_id", str(user_id)
            ).eq("question_id", question["id"]).execute()

    update_scope_progress(user_id, question["mode"], question["exam_scope"], round_number)

    return inserted.data[0]
