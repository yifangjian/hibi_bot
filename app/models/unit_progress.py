from datetime import datetime

from pydantic import BaseModel

from app.models.question import Mode


class UnitProgress(BaseModel):
    user_id: str
    mode: Mode
    unit_number: int
    all_attempted: bool = False
    all_wrong_resolved: bool = False
    current_round: int = 1
    updated_at: datetime
