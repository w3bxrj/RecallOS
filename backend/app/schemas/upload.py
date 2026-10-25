from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    """Response returned upon successful file upload and job creation."""
    deck_id: int
    job_id: int


class JobResponse(BaseModel):
    """Job status polling response."""
    id: int
    deck_id: Optional[int] = None
    status: str
    total_chunks: int
    done_chunks: int
    cards_created: int
    error_message: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
