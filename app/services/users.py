import logging
from uuid import UUID

from app.db.client import supabase
from app.services import email_client, line_client

logger = logging.getLogger("hibi_bot.users")


def _notify_new_pending_user(line_user_id: str) -> None:
    """新使用者第一次互動時寄一封 email 通知研究者，方便對照問卷名單決定要不要開通。
    只在真正建立新使用者的當下觸發一次，不會因為使用者在審核期間反覆傳訊息而重複寄信。
    這只是輔助通知，寄信失敗不該擋住使用者的建立或後續回覆流程。
    """
    try:
        display_name = line_client.get_display_name(line_user_id)
    except Exception:
        logger.exception("failed to fetch LINE display name for new pending user")
        display_name = "（查詢顯示名稱失敗）"

    try:
        email_client.send_notification_email(
            subject="hibi_bot 新使用者待審核",
            body=(
                f"有新的使用者第一次使用 hibi_bot，狀態為 pending，等待確認資格：\n\n"
                f"顯示名稱：{display_name}\n"
                f"line_user_id：{line_user_id}\n\n"
                f"確認資格後，請告訴 Claude 要開通這位使用者。"
            ),
        )
    except Exception:
        logger.exception("failed to send new-pending-user notification email")


def get_or_create_user(line_user_id: str) -> tuple[UUID, str]:
    """回傳 (user_id, status)。status 為 'pending'（新使用者，等待研究者確認資格）、
    'active'（確認是研究參與者，正常使用）或 'inactive'（確認不是研究參與者，已停用）。
    呼叫端（webhook.py）依這個狀態決定要不要放行，但不論哪個狀態都不會刪除這個使用者
    任何既有的歷史資料。"""
    existing = supabase.table("users").select("id, status").eq("line_user_id", line_user_id).execute()
    if existing.data:
        row = existing.data[0]
        return UUID(row["id"]), row["status"]

    created = supabase.table("users").insert({"line_user_id": line_user_id}).execute()
    row = created.data[0]
    _notify_new_pending_user(line_user_id)
    return UUID(row["id"]), row["status"]
