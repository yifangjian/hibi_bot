from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PushLog(BaseModel):
    id: UUID
    user_id: UUID
    challenge_id: UUID
    pushed_at: datetime
