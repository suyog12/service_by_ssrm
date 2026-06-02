from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID
from decimal import Decimal
from enum import Enum


class KOTStation(str, Enum):
    kitchen = "kitchen"
    bar = "bar"
    grill = "grill"


#  Category schemas 

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sort_order: int = 0

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Category name cannot be empty")
        return v.strip()


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Category name cannot be empty")
        return v.strip() if v else v


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool

    class Config:
        from_attributes = True


#  Item schemas 

class MenuItemCreate(BaseModel):
    name: str
    category_id: UUID
    description: Optional[str] = None
    price: Decimal
    tax_rate: Decimal = Decimal("13.00")
    station: Optional[KOTStation] = None
    is_available: bool = True
    image_url: Optional[str] = None
    sort_order: int = 0

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Item name cannot be empty")
        return v.strip()

    @field_validator("price")
    @classmethod
    def price_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Price cannot be negative")
        return v

    @field_validator("tax_rate")
    @classmethod
    def tax_rate_valid(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("Tax rate must be between 0 and 100")
        return v


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[UUID] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    station: Optional[KOTStation] = None
    is_available: Optional[bool] = None
    image_url: Optional[str] = None
    sort_order: Optional[int] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Item name cannot be empty")
        return v.strip() if v else v

    @field_validator("price")
    @classmethod
    def price_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Price cannot be negative")
        return v


class MenuItemResponse(BaseModel):
    id: UUID
    name: str
    category_id: UUID
    category_name: Optional[str] = None
    description: Optional[str] = None
    price: Decimal
    tax_rate: Decimal
    station: Optional[str] = None
    is_available: bool
    image_url: Optional[str] = None
    sort_order: int

    class Config:
        from_attributes = True