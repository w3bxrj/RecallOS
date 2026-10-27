from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, computed_field


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
    is_vision: bool = False
    notice: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

    @computed_field
    @property
    def vision_mode(self) -> bool:
        return self.is_vision

    model_config = ConfigDict(from_attributes=True)
