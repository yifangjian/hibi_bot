from datetime import datetime

from pydantic import BaseModel

from app.models.question import Mode


class ScopeProgress(BaseModel):
    user_id: str
    mode: Mode
    exam_scope: str
    all_attempted: bool = False
    all_wrong_resolved: bool = False
    current_round: int = 1
    updated_at: datetime
