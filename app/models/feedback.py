from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class FeedbackLog(BaseModel):
    id: UUID
    attempt_log_id: UUID
    ai_generated_text: Optional[str] = None
    model_used: Optional[str] = None
    human_reviewed: bool = False
    created_at: datetime
