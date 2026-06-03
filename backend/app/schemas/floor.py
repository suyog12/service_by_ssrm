from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID


# Section schemas 

class SectionCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Section name cannot be empty")
        return v.strip()


class SectionUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Section name cannot be empty")
        return v.strip() if v else v


class SectionResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool

    class Config:
        from_attributes = True


# Table schemas 

class TableCreate(BaseModel):
    table_number: str
    capacity: int = 4
    section_id: Optional[UUID] = None

    @field_validator("table_number")
    @classmethod
    def table_number_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Table number cannot be empty")
        return v.strip()

    @field_validator("capacity")
    @classmethod
    def capacity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Capacity must be at least 1")
        return v


class TableUpdate(BaseModel):
    table_number: Optional[str] = None
    capacity: Optional[int] = None
    section_id: Optional[UUID] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: Optional[str]) -> Optional[str]:
        valid = {"available", "occupied", "reserved", "needs_cleaning"}
        if v is not None and v not in valid:
            raise ValueError(f"Status must be one of {valid}")
        return v


class TableResponse(BaseModel):
    id: UUID
    table_number: str
    capacity: int
    status: str
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None

    class Config:
        from_attributes = True