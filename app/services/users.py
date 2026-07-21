from uuid import UUID

from app.db.client import supabase


def get_or_create_user(line_user_id: str) -> tuple[UUID, bool]:
    """回傳 (user_id, is_active)。is_active 為 False 代表這個使用者已被停用（例如確認
    不是研究參與者），呼叫端（webhook.py）要擋下後續互動、只回覆固定的停用說明，但不會
    刪除這個使用者任何既有的歷史資料。"""
    existing = supabase.table("users").select("id, is_active").eq("line_user_id", line_user_id).execute()
    if existing.data:
        row = existing.data[0]
        return UUID(row["id"]), row["is_active"]

    created = supabase.table("users").insert({"line_user_id": line_user_id}).execute()
    row = created.data[0]
    return UUID(row["id"]), row["is_active"]
