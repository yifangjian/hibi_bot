from uuid import UUID

from app.db.client import supabase


def get_scope_question_ids(mode: str, exam_scope: str) -> set[str]:
    rows = (
        supabase.table("questions")
        .select("id")
        .eq("mode", mode)
        .eq("exam_scope", exam_scope)
        .is_("parent_question_id", "null")
        .execute()
        .data
    )
    return {row["id"] for row in rows}


def count_attempted_in_scope(user_id: UUID, scope_question_ids: set[str], round_number: int) -> int:
    attempted = (
        supabase.table("attempts_log")
        .select("question_id")
        .eq("user_id", str(user_id))
        .eq("round_number", round_number)
        .execute()
        .data
    )
    return len({row["question_id"] for row in attempted} & scope_question_ids)


def count_wrong_in_scope(user_id: UUID, scope_question_ids: set[str]) -> int:
    wrong = (
        supabase.table("wrong_question_state")
        .select("question_id")
        .eq("user_id", str(user_id))
        .eq("status", "wrong")
        .execute()
        .data
    )
    return len({row["question_id"] for row in wrong} & scope_question_ids)


def update_scope_progress(user_id: UUID, mode: str, exam_scope: str) -> None:
    existing = (
        supabase.table("scope_progress")
        .select("current_round")
        .eq("user_id", str(user_id))
        .eq("mode", mode)
        .eq("exam_scope", exam_scope)
        .execute()
        .data
    )
    current_round = existing[0]["current_round"] if existing else 1

    scope_question_ids = get_scope_question_ids(mode, exam_scope)
    total_count = len(scope_question_ids)

    # 只看「當前這一輪」的作答紀錄，避免重置後被過去輪次的紀錄誤判成已全部作答
    attempted_count = count_attempted_in_scope(user_id, scope_question_ids, current_round)
    all_attempted = total_count > 0 and attempted_count >= total_count

    wrong_count = count_wrong_in_scope(user_id, scope_question_ids)
    all_wrong_resolved = wrong_count == 0

    supabase.table("scope_progress").upsert(
        {
            "user_id": str(user_id),
            "mode": mode,
            "exam_scope": exam_scope,
            "all_attempted": all_attempted,
            "all_wrong_resolved": all_wrong_resolved,
            "current_round": current_round,
        }
    ).execute()
