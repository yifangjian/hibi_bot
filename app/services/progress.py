from uuid import UUID

from app.db.client import supabase


def update_unit_progress(user_id: UUID, mode: str, unit_number: int) -> None:
    existing = (
        supabase.table("unit_progress")
        .select("current_round")
        .eq("user_id", str(user_id))
        .eq("mode", mode)
        .eq("unit_number", unit_number)
        .execute()
        .data
    )
    current_round = existing[0]["current_round"] if existing else 1

    unit_questions = (
        supabase.table("questions")
        .select("id")
        .eq("mode", mode)
        .eq("unit_number", unit_number)
        .is_("parent_question_id", "null")
        .execute()
        .data
    )
    unit_question_ids = {row["id"] for row in unit_questions}
    total_count = len(unit_question_ids)

    # 只看「當前這一輪」的作答紀錄，避免重置後被過去輪次的紀錄誤判成已全部作答
    attempted = (
        supabase.table("attempts_log")
        .select("question_id")
        .eq("user_id", str(user_id))
        .eq("round_number", current_round)
        .execute()
        .data
    )
    attempted_ids_in_unit = {row["question_id"] for row in attempted} & unit_question_ids
    all_attempted = total_count > 0 and len(attempted_ids_in_unit) >= total_count

    wrong = (
        supabase.table("wrong_question_state")
        .select("question_id")
        .eq("user_id", str(user_id))
        .eq("status", "wrong")
        .execute()
        .data
    )
    wrong_ids_in_unit = {row["question_id"] for row in wrong} & unit_question_ids
    all_wrong_resolved = len(wrong_ids_in_unit) == 0

    supabase.table("unit_progress").upsert(
        {
            "user_id": str(user_id),
            "mode": mode,
            "unit_number": unit_number,
            "all_attempted": all_attempted,
            "all_wrong_resolved": all_wrong_resolved,
            "current_round": current_round,
        }
    ).execute()
