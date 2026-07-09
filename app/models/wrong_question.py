from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

WrongQuestionStatus = Literal["wrong", "resolved"]


class WrongQuestionState(BaseModel):
    user_id: UUID
    question_id: UUID
    status: WrongQuestionStatus
    updated_at: datetime
