from datetime import datetime, timezone
from uuid import UUID

from app.db.client import supabase
from app.services import line_client
from app.services.progress import count_wrong_in_scope
from app.services.question_picker import get_current_scope_and_round


def handle_reset_unit(user_id: UUID, params: dict, reply_token: str) -> None:
    """重置條件：該模式目前範圍須 all_attempted 且 all_wrong_resolved 皆為 true 才允許。
    重置只把 scope_progress 的追蹤狀態打回起點（current_round +1），不動 attempts_log／
    wrong_question_state 這些歷史紀錄，過去每一輪的資料完整保留。
    """
    mode = params.get("mode")

    exam_scope, _ = get_current_scope_and_round(user_id, mode)
    if exam_scope is None:
        line_client.reply_text(reply_token, f"「{mode}」目前還沒有指定教學範圍，無法重置。")
        return

    progress_rows = (
        supabase.table("scope_progress")
        .select("*")
        .eq("user_id", str(user_id))
        .eq("mode", mode)
        .eq("exam_scope", exam_scope)
        .execute()
        .data
    )
    if not progress_rows:
        line_client.reply_text(reply_token, "這個範圍還沒開始作答，還不能重置喔。")
        return

    progress = progress_rows[0]

    if not progress["all_attempted"]:
        line_client.reply_text(reply_token, "還有題目尚未作答完，加油！")
        return

    if not progress["all_wrong_resolved"]:
        wrong_count = count_wrong_in_scope(user_id, mode, exam_scope)
        line_client.reply_text(reply_token, f"你還有 {wrong_count} 題錯題尚未複習完成，複習完才能重置喔")
        return

    new_round = progress["current_round"] + 1
    supabase.table("scope_progress").update(
        {
            "current_round": new_round,
            "all_attempted": False,
            "all_wrong_resolved": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("user_id", str(user_id)).eq("mode", mode).eq("exam_scope", exam_scope).execute()

    line_client.reply_text(reply_token, f"已重置！你現在進入第 {new_round} 輪，加油 💪")
