from typing import Any, Optional
from uuid import UUID

from app.db.client import supabase
from app.services.progress import update_unit_progress


def finalize_attempt(
    user_id: UUID,
    question: dict[str, Any],
    is_correct: bool,
    selected_option: Optional[str],
    answer_detail: Optional[dict[str, Any]] = None,
    attempt_type: str = "first",
) -> dict[str, Any]:
    """寫入一筆 attempts_log，更新 wrong_question_state 與 unit_progress。

    question 為該題的「代表列」：単語/言語知識為題目本身，諺則為第一階段列
    （整題的識別以第一階段的 id 為準）。
    """
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

    update_unit_progress(user_id, question["mode"], question["unit_number"])

    return inserted.data[0]
