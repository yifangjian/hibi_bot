from datetime import date
from uuid import UUID

from pydantic import BaseModel


class AiConversationUsage(BaseModel):
    user_id: UUID
    usage_date: date
    turn_count: int = 0
