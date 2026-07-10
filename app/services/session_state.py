from typing import Any, Optional
from uuid import UUID

from app.db.client import supabase


def get_session_state(user_id: UUID) -> Optional[dict[str, Any]]:
    res = supabase.table("user_session_state").select("*").eq("user_id", str(user_id)).execute()
    return res.data[0] if res.data else None


def set_session_state(user_id: UUID, pending_action: str, context: Optional[dict[str, Any]] = None) -> None:
    supabase.table("user_session_state").upsert(
        {"user_id": str(user_id), "pending_action": pending_action, "context": context}
    ).execute()


def clear_session_state(user_id: UUID) -> None:
    supabase.table("user_session_state").upsert(
        {"user_id": str(user_id), "pending_action": None, "context": None}
    ).execute()
