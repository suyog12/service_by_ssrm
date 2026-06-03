from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID
from decimal import Decimal
from enum import Enum


class OrderType(str, Enum):
    dine_in = "dine_in"
    takeaway = "takeaway"
    room_service = "room_service"


class OrderStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    ready = "ready"
    served = "served"
    billed = "billed"
    cancelled = "cancelled"


class OrderItemStatus(str, Enum):
    pending = "pending"
    preparing = "preparing"
    ready = "ready"
    served = "served"
    cancelled = "cancelled"


# Order schemas 
class OrderCreate(BaseModel):
    order_type: OrderType = OrderType.dine_in
    table_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    notes: Optional[str] = None

    @field_validator("table_id")
    @classmethod
    def table_required_for_dine_in(cls, v, info):
        return v


class OrderResponse(BaseModel):
    id: UUID
    order_number: str
    order_type: str
    status: str
    table_id: Optional[UUID] = None
    table_number: Optional[str] = None
    notes: Optional[str] = None
    item_count: int = 0

    class Config:
        from_attributes = True


# Order item schemas 
class OrderItemAdd(BaseModel):
    menu_item_id: UUID
    quantity: int = 1
    special_instruction: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        return v


class OrderItemResponse(BaseModel):
    id: UUID
    order_id: UUID
    menu_item_id: UUID
    item_name: str
    quantity: int
    unit_price: Decimal
    special_instruction: Optional[str] = None
    status: str
    station: Optional[str] = None

    class Config:
        from_attributes = True


class OrderItemStatusUpdate(BaseModel):
    status: OrderItemStatus


class OrderStatusUpdate(BaseModel):
    status: OrderStatus