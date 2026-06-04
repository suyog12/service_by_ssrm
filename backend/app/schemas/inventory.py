from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime


# Supplier 

class SupplierCreate(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    pan_number: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Supplier name cannot be empty")
        return v.strip()


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    pan_number: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Supplier name cannot be empty")
        return v.strip() if v else v


class SupplierResponse(BaseModel):
    id: UUID
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    pan_number: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


# Stock Addition 

class StockAddRequest(BaseModel):
    ingredient_id: UUID
    quantity: Decimal
    expiry_date: Optional[date] = None
    cost_per_unit: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v


class StockAddResponse(BaseModel):
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    quantity_added: Decimal
    current_stock: Decimal
    batch_id: UUID

    class Config:
        from_attributes = True


# Stock Adjustment 

class StockAdjustRequest(BaseModel):
    ingredient_id: UUID
    new_stock: Decimal
    reason: str

    @field_validator("new_stock")
    @classmethod
    def stock_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Stock cannot be negative")
        return v

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Reason cannot be empty")
        return v.strip()


class StockAdjustResponse(BaseModel):
    id: UUID
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    previous_stock: Decimal
    new_stock: Decimal
    reason: str
    adjusted_by: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# Reorder Alert 

class ReorderAlertItem(BaseModel):
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    current_stock: Decimal
    reorder_level: Decimal

    class Config:
        from_attributes = True


# Purchase Order 

class POItemAdd(BaseModel):
    ingredient_id: UUID
    ordered_qty: Decimal
    unit_price: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("ordered_qty")
    @classmethod
    def qty_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Ordered quantity must be greater than zero")
        return v


class POItemResponse(BaseModel):
    id: UUID
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    ordered_qty: Decimal
    received_qty: Decimal
    rejected_qty: Decimal
    unit_price: Optional[Decimal] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class POCreate(BaseModel):
    supplier_id: UUID
    expected_date: Optional[date] = None
    notes: Optional[str] = None


class POResponse(BaseModel):
    id: UUID
    po_number: str
    supplier_id: UUID
    supplier_name: str
    status: str
    raised_by: UUID
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    expected_date: Optional[date] = None
    notes: Optional[str] = None
    total_amount: Optional[Decimal] = None
    items: list[POItemResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class POReceiveItem(BaseModel):
    po_item_id: UUID
    received_qty: Decimal
    rejected_qty: Decimal = Decimal("0")
    expiry_date: Optional[date] = None

    @field_validator("received_qty")
    @classmethod
    def qty_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Received quantity cannot be negative")
        return v