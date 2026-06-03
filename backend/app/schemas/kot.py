from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class KOTResponse(BaseModel):
    id: UUID
    order_id: UUID
    kot_number: str
    kot_type: str
    display_status: str
    assigned_to: Optional[UUID] = None
    printed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class KOTAssign(BaseModel):
    assigned_to: UUID


class KOTStatusUpdate(BaseModel):
    display_status: str