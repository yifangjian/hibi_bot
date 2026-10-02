from uuid import UUID

from app.db.client import supabase


def get_or_create_user(line_user_id: str) -> tuple[UUID, str]:
    """回傳 (user_id, status)。status 為 'pending'（還沒輸入開通碼）、'active'（已用開通碼
    開通，正常使用）或 'inactive'（研究者手動停用）。新使用者一律建立為 'pending'，要輸入
    研究者發的開通碼才會變成 'active'（見 app/services/access_codes.py）。呼叫端
    （webhook.py）依這個狀態決定要不要放行，但不論哪個狀態都不會刪除這個使用者任何既有的
    歷史資料。"""
    existing = supabase.table("users").select("id, status").eq("line_user_id", line_user_id).execute()
    if existing.data:
        row = existing.data[0]
        return UUID(row["id"]), row["status"]

    created = supabase.table("users").insert({"line_user_id": line_user_id}).execute()
    row = created.data[0]
    return UUID(row["id"]), row["status"]
