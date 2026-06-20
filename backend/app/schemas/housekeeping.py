from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from decimal import Decimal


# Housekeeping Task Schemas

class HousekeepingTaskCreate(BaseModel):
    room_id: UUID
    task_type: str = Field(default="cleaning")
    assigned_to: Optional[UUID] = None
    notes: Optional[str] = None


class HousekeepingTaskUpdate(BaseModel):
    task_type: Optional[str] = None
    assigned_to: Optional[UUID] = None
    status: Optional[str] = None
    notes: Optional[str] = None


# Housekeeping Kit Schemas

class HousekeepingKitItemCreate(BaseModel):
    ingredient_id: UUID
    quantity_per_turn: Decimal = Field(..., gt=0)


# Minibar Schemas

class MinibarItemCreate(BaseModel):
    ingredient_id: UUID
    quantity: Decimal = Field(..., gt=0)