from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    exam_date: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    exam_date: Optional[datetime] = None
