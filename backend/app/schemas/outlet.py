from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


VALID_OUTLET_TYPES = ("restaurant", "bar", "cafe", "hotel", "banquet", "other")
VALID_KITCHEN_MODES = (
    "paperless",
    "single_printer",
    "station_printer",
    "station_display",
    "station_display_print",
)
OUTLET_LIMITS = {
    "ez": 1,
    "pro": 3,
    "max": None,
    "enterprise": None,
}


class OutletCreate(BaseModel):
    name: str
    type: str = "restaurant"
    address: Optional[str] = None
    phone: Optional[str] = None
    kitchen_mode: str = "single_printer"
    menu_source_id: Optional[UUID] = None
    inventory_source_id: Optional[UUID] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Outlet name cannot be empty")
        return v.strip()

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        if v not in VALID_OUTLET_TYPES:
            raise ValueError(f"type must be one of: {', '.join(VALID_OUTLET_TYPES)}")
        return v

    @field_validator("kitchen_mode")
    @classmethod
    def kitchen_mode_valid(cls, v: str) -> str:
        if v not in VALID_KITCHEN_MODES:
            raise ValueError(f"kitchen_mode must be one of: {', '.join(VALID_KITCHEN_MODES)}")
        return v


class OutletUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    kitchen_mode: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Outlet name cannot be empty")
        return v.strip() if v else v

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_OUTLET_TYPES:
            raise ValueError(f"type must be one of: {', '.join(VALID_OUTLET_TYPES)}")
        return v

    @field_validator("kitchen_mode")
    @classmethod
    def kitchen_mode_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_KITCHEN_MODES:
            raise ValueError(f"kitchen_mode must be one of: {', '.join(VALID_KITCHEN_MODES)}")
        return v


class OutletResponse(BaseModel):
    id: UUID
    name: str
    type: str
    address: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    kitchen_mode: str
    menu_source_id: Optional[UUID] = None
    inventory_source_id: Optional[UUID] = None
    is_default: bool
    sort_order: int
    created_at: datetime

    class Config:
        from_attributes = True