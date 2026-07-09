from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

AttemptType = Literal["first", "review"]


class AttemptLog(BaseModel):
    id: UUID
    user_id: UUID
    question_id: UUID
    selected_option: Optional[str] = None
    is_correct: Optional[bool] = None
    attempt_type: AttemptType
    pushed_at: Optional[datetime] = None
    responded_at: datetime
