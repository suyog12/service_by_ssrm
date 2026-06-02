from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID
from decimal import Decimal


# Ingredient schemas 

class IngredientCreate(BaseModel):
    name: str
    unit: str
    reorder_level: Decimal = Decimal("0")
    cost_per_unit: Optional[Decimal] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Ingredient name cannot be empty")
        return v.strip()

    @field_validator("unit")
    @classmethod
    def unit_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Unit cannot be empty")
        return v.strip()


class IngredientUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    reorder_level: Optional[Decimal] = None
    cost_per_unit: Optional[Decimal] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Ingredient name cannot be empty")
        return v.strip() if v else v


class IngredientResponse(BaseModel):
    id: UUID
    name: str
    unit: str
    reorder_level: Decimal
    current_stock: Decimal
    cost_per_unit: Optional[Decimal] = None

    class Config:
        from_attributes = True


# Item ingredient linking schemas 

class ItemIngredientAdd(BaseModel):
    ingredient_id: UUID
    quantity_used: Decimal

    @field_validator("quantity_used")
    @classmethod
    def quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantity used must be greater than zero")
        return v


class ItemIngredientUpdate(BaseModel):
    quantity_used: Decimal

    @field_validator("quantity_used")
    @classmethod
    def quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantity used must be greater than zero")
        return v


class ItemIngredientResponse(BaseModel):
    id: UUID
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    quantity_used: Decimal

    class Config:
        from_attributes = True