from uuid import UUID

from app.db.client import supabase


def get_or_create_user(line_user_id: str) -> UUID:
    existing = supabase.table("users").select("id").eq("line_user_id", line_user_id).execute()
    if existing.data:
        return UUID(existing.data[0]["id"])

    created = supabase.table("users").insert({"line_user_id": line_user_id}).execute()
    return UUID(created.data[0]["id"])
