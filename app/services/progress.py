from uuid import UUID

from app.db.client import fetch_all_rows, supabase
from app.services.question_picker import get_scope_progress_index


def question_number_map(index: dict[int, list[str]]) -> dict[str, int]:
    """列 id -> question_number，供把 attempts_log/wrong_question_state 記錄的 row id
    換算回題號再去重用。呼叫端應該只抓一次 get_scope_progress_index 再重複使用這個 map，
    避免同一個範圍的題目清單被重複查詢。
    """
    return {rid: number for number, ids in index.items() for rid in ids}


def count_attempted_in_scope(user_id: UUID, id_to_number: dict[str, int], round_number: int) -> int:
    attempted = fetch_all_rows(
        lambda: supabase.table("attempts_log")
        .select("question_id")
        .eq("user_id", str(user_id))
        .eq("round_number", round_number)
    )
    numbers = {id_to_number[row["question_id"]] for row in attempted if row["question_id"] in id_to_number}
    return len(numbers)


def count_wrong_in_scope(user_id: UUID, id_to_number: dict[str, int]) -> int:
    wrong = fetch_all_rows(
        lambda: supabase.table("wrong_question_state")
        .select("question_id")
        .eq("user_id", str(user_id))
        .eq("status", "wrong")
    )
    numbers = {id_to_number[row["question_id"]] for row in wrong if row["question_id"] in id_to_number}
    return len(numbers)


def update_scope_progress(user_id: UUID, mode: str, exam_scope: str, current_round: int) -> None:
    """current_round 由呼叫端傳入（呼叫端多半已經為了寫入 attempts_log 查過一次，避免
    這裡再查一次一樣的 scope_progress row）。"""
    index = get_scope_progress_index(mode, exam_scope)
    id_to_number = question_number_map(index)
    total_count = len(index)

    # 只看「當前這一輪」的作答紀錄，避免重置後被過去輪次的紀錄誤判成已全部作答
    attempted_count = count_attempted_in_scope(user_id, id_to_number, current_round)
    all_attempted = total_count > 0 and attempted_count >= total_count

    wrong_count = count_wrong_in_scope(user_id, id_to_number)
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
