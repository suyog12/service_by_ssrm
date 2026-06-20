from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


# Table Reservation Schemas

class ReservationCreate(BaseModel):
    customer_name: str
    customer_phone: str
    party_size: int
    reserved_at: datetime
    reserved_until: datetime
    notes: Optional[str] = None

    @field_validator("customer_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Customer name cannot be empty")
        return v.strip()

    @field_validator("customer_phone")
    @classmethod
    def phone_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Customer phone cannot be empty")
        return v.strip()

    @field_validator("party_size")
    @classmethod
    def party_size_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Party size must be at least 1")
        return v

    @model_validator(mode="after")
    def check_time_window(self):
        if self.reserved_until <= self.reserved_at:
            raise ValueError("reserved_until must be after reserved_at")
        return self


class ReservationUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    party_size: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: Optional[str]) -> Optional[str]:
        valid = {"confirmed", "cancelled", "completed", "no_show"}
        if v is not None and v not in valid:
            raise ValueError(f"Status must be one of {valid}")
        return v

    @field_validator("party_size")
    @classmethod
    def party_size_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("Party size must be at least 1")
        return v


class ReservationResponse(BaseModel):
    id: UUID
    outlet_id: UUID
    table_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    party_size: Optional[int] = None
    reserved_at: datetime
    duration_mins: Optional[int] = None
    reserved_until: Optional[datetime] = None
    status: str
    notes: Optional[str] = None
    merged_table_ids: list[UUID] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True