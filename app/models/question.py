from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

Mode = Literal["vocab", "proverb", "language_knowledge"]
Stage = Literal["semantic_choice", "situational_choice", "reading_input"]


class QuestionOption(BaseModel):
    id: str
    text: str


class Question(BaseModel):
    id: UUID
    mode: Mode
    unit_number: int
    stage: Optional[Stage] = None
    parent_question_id: Optional[UUID] = None
    context_sentence: Optional[str] = None
    blank_marker: Optional[str] = None
    options: Optional[list[QuestionOption]] = None
    correct_option: Optional[str] = None
    explanation_rule: Optional[str] = None
    question_number: Optional[int] = None
    created_at: datetime
