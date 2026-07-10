from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel

PendingAction = Literal["awaiting_reading_input", "awaiting_ai_tutor_question_number"]


class UserSessionState(BaseModel):
    user_id: UUID
    pending_action: Optional[PendingAction] = None
    context: Optional[dict[str, Any]] = None
    updated_at: datetime
