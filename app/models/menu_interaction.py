from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class MenuInteractionLog(BaseModel):
    id: UUID
    user_id: UUID
    action: str
    mode: Optional[str] = None
    clicked_at: datetime
