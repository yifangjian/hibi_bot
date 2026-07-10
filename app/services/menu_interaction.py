from typing import Optional
from uuid import UUID

from app.db.client import supabase


def log_menu_interaction(user_id: UUID, action: Optional[str], mode: Optional[str] = None) -> None:
    supabase.table("menu_interaction_log").insert(
        {"user_id": str(user_id), "action": action, "mode": mode}
    ).execute()
