from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class ChallengeQuestionRef(BaseModel):
    mode: str
    question_id: str


class ChallengeResult(BaseModel):
    question_id: str
    is_correct: bool


class DailyChallenge(BaseModel):
    id: UUID
    user_id: UUID
    challenge_date: date
    questions: list[dict[str, Any]]
    results: list[dict[str, Any]] = []
    current_index: int = 0
    completed: bool = False
    completed_at: Optional[datetime] = None
    created_at: datetime
