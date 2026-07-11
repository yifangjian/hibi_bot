from uuid import UUID

from app.db.client import supabase
from app.services.question_picker import get_scope_candidates


def get_scope_question_numbers(mode: str, exam_scope: str) -> set[int]:
    return set(get_scope_candidates(mode, exam_scope).keys())


def _question_number_map(mode: str, exam_scope: str) -> dict[str, int]:
    """列 id -> question_number。諺的變體列 id 每次隨機出題才決定，本身不能當題目識別，
    所以計算「這一輪/這個範圍答過幾題、錯幾題」時都要先透過這個 map 換算回題號再去重。
    """
    groups = get_scope_candidates(mode, exam_scope)
    return {row["id"]: number for number, rows in groups.items() for row in rows}


def count_attempted_in_scope(user_id: UUID, mode: str, exam_scope: str, round_number: int) -> int:
    id_to_number = _question_number_map(mode, exam_scope)
    attempted = (
        supabase.table("attempts_log")
        .select("question_id")
        .eq("user_id", str(user_id))
        .eq("round_number", round_number)
        .execute()
        .data
    )
    numbers = {id_to_number[row["question_id"]] for row in attempted if row["question_id"] in id_to_number}
    return len(numbers)


def count_wrong_in_scope(user_id: UUID, mode: str, exam_scope: str) -> int:
    id_to_number = _question_number_map(mode, exam_scope)
    wrong = (
        supabase.table("wrong_question_state")
        .select("question_id")
        .eq("user_id", str(user_id))
        .eq("status", "wrong")
        .execute()
        .data
    )
    numbers = {id_to_number[row["question_id"]] for row in wrong if row["question_id"] in id_to_number}
    return len(numbers)


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

    total_count = len(get_scope_question_numbers(mode, exam_scope))

    # 只看「當前這一輪」的作答紀錄，避免重置後被過去輪次的紀錄誤判成已全部作答
    attempted_count = count_attempted_in_scope(user_id, mode, exam_scope, current_round)
    all_attempted = total_count > 0 and attempted_count >= total_count

    wrong_count = count_wrong_in_scope(user_id, mode, exam_scope)
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
