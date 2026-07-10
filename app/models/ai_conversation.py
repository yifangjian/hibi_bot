from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

ConversationRole = Literal["user", "assistant"]


class AiConversationLogEntry(BaseModel):
    id: UUID
    user_id: UUID
    question_id: UUID
    role: ConversationRole
    message: Optional[str] = None
    created_at: datetime
