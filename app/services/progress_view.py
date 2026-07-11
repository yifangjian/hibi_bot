from typing import Any
from uuid import UUID

from app.db.client import supabase
from app.services import flex_templates, line_client
from app.services.progress import count_attempted_in_scope, count_wrong_in_scope, get_scope_question_ids
from app.services.question_picker import get_current_scope_and_round

MODES = ["vocab", "proverb", "language_knowledge"]


def _mode_progress_summary(user_id: UUID, mode: str) -> dict[str, Any]:
    exam_scope, current_round = get_current_scope_and_round(user_id, mode)
    if exam_scope is None:
        return {"mode": mode, "no_data": True}

    scope_question_ids = get_scope_question_ids(mode, exam_scope)
    total = len(scope_question_ids)
    attempted_count = count_attempted_in_scope(user_id, scope_question_ids, current_round)
    wrong_count = count_wrong_in_scope(user_id, scope_question_ids)

    return {
        "mode": mode,
        "no_data": False,
        "exam_scope": exam_scope,
        "current_round": current_round,
        "attempted_count": attempted_count,
        "total": total,
        "wrong_count": wrong_count,
    }


def _completed_challenge_count(user_id: UUID) -> int:
    rows = (
        supabase.table("daily_challenge")
        .select("id")
        .eq("user_id", str(user_id))
        .eq("completed", True)
        .execute()
        .data
    )
    return len(rows)


def show_progress(user_id: UUID, reply_token: str) -> None:
    summaries = [_mode_progress_summary(user_id, mode) for mode in MODES]
    completed_count = _completed_challenge_count(user_id)
    line_client.reply_flex(
        reply_token,
        alt_text="我的進度",
        contents=flex_templates.build_progress_card(summaries, completed_count),
    )
