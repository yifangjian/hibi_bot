from datetime import datetime

from pydantic import BaseModel

from app.models.question import Mode


class ActiveExamScope(BaseModel):
    mode: Mode
    exam_scope: str
    updated_at: datetime
