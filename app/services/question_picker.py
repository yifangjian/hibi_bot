import random
from typing import Any, Optional
from uuid import UUID

from app.db.client import supabase


def get_question(question_id: str) -> Optional[dict[str, Any]]:
    res = supabase.table("questions").select("*").eq("id", str(question_id)).execute()
    return res.data[0] if res.data else None


def get_proverb_stage2(stage1_question_id: str) -> Optional[dict[str, Any]]:
    """諺第二階段（読み方）：與第一階段共用同一個 question_number，用 stage 區分。"""
    stage1 = get_question(stage1_question_id)
    if not stage1:
        return None
    res = (
        supabase.table("questions")
        .select("*")
        .eq("mode", "proverb")
        .eq("exam_scope", stage1["exam_scope"])
        .eq("question_number", stage1["question_number"])
        .eq("stage", "reading_input")
        .execute()
    )
    return res.data[0] if res.data else None


def find_question_by_number(mode: str, exam_scope: str, question_number: int) -> Optional[dict[str, Any]]:
    """依人類可讀題號查詢（供 AI 助教用）。題號只在同一個 (mode, exam_scope) 內唯一——每次
    考期換 exam_scope 都會重新從 1 編號，所以查詢一定要限定在目前的範圍內，否則不同考期會
    撞號。単語/言語知識每個題號對應一筆。諺同一題號下可能有 semantic_choice/situational_choice
    兩種變體（reading_input 不算獨立一題，排除），固定取 stage 字母序較小的一筆（semantic_choice）
    當代表，兩者內容為同一句諺語的不同出題形式，解釋依據大同小異。
    """
    rows = (
        supabase.table("questions")
        .select("*")
        .eq("mode", mode)
        .eq("exam_scope", exam_scope)
        .eq("question_number", question_number)
        .execute()
        .data
    )
    candidates = [r for r in rows if r.get("stage") != "reading_input"]
    if not candidates:
        return None
    candidates.sort(key=lambda r: r.get("stage") or "")
    return candidates[0]


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


def get_scope_candidates(mode: str, exam_scope: str) -> dict[int, list[dict[str, Any]]]:
    """這個範圍所有可作為「一題」的候選列，依 question_number 分組。reading_input 永遠
    排除（它不是獨立一題，只是諺第二階段的附屬列）。単語/言語知識每個 question_number
    底下固定只有 1 筆；諺可能有 1～2 筆（semantic_choice/situational_choice，出題時隨機
    擇一）。
    """
    rows = (
        supabase.table("questions")
        .select("*")
        .eq("mode", mode)
        .eq("exam_scope", exam_scope)
        .execute()
        .data
    )
    groups: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("stage") == "reading_input":
            continue
        groups.setdefault(row["question_number"], []).append(row)
    return groups


def _pick_representative(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return random.choice(rows) if len(rows) > 1 else rows[0]


def get_available_questions_in_scope(
    user_id: str, mode: str, exam_scope: str, round_number: int
) -> list[dict[str, Any]]:
    """這個範圍在目前輪次還沒作答過的題目（依 question_number 排序），一個 question_number
    回傳一筆代表列。判斷「是否已作答過」以 question_number 為準，不是以列 id 為準——諺同一
    題號不管這次隨機抽到哪個變體，只要這個題號本輪已經作答過，就不會再被選中。
    """
    groups = get_scope_candidates(mode, exam_scope)
    id_to_number = {row["id"]: number for number, rows in groups.items() for row in rows}

    attempted_ids_this_round = {
        row["question_id"]
        for row in supabase.table("attempts_log")
        .select("question_id")
        .eq("user_id", str(user_id))
        .eq("round_number", round_number)
        .execute()
        .data
    }
    attempted_numbers = {id_to_number[qid] for qid in attempted_ids_this_round if qid in id_to_number}

    available_numbers = sorted(n for n in groups if n not in attempted_numbers)
    return [_pick_representative(groups[n]) for n in available_numbers]


def pick_next_question(user_id: UUID, mode: str) -> Optional[dict[str, Any]]:
    """挑下一題：目前範圍、目前輪次裡還沒作答過的題目（依 question_number 排序取第一個，
    諺會在該題號的變體之間隨機擇一）。若這一輪已全部作答完（理論上此時應先重置），保底回
    傳題號最小的一題，避免卡住無法互動。
    """
    exam_scope, current_round = get_current_scope_and_round(user_id, mode)
    if exam_scope is None:
        return None

    available = get_available_questions_in_scope(user_id, mode, exam_scope, current_round)
    if available:
        return available[0]

    groups = get_scope_candidates(mode, exam_scope)
    if not groups:
        return None
    first_number = min(groups)
    return _pick_representative(groups[first_number])


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
        .order("question_number")
        .execute()
        .data
    )
    for question in questions:
        if question["id"] in wrong_ids:
            return question
    return None
