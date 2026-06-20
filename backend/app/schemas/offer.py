from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from uuid import UUID
from datetime import time
from decimal import Decimal


VALID_OFFER_TYPES = {"flat", "percentage", "item_specific", "happy_hour", "combo"}
VALID_APPLIES_TO = {"all", "category", "item"}


class OfferCreate(BaseModel):
    name: str
    offer_type: str
    discount_value: Decimal
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    days_of_week: Optional[list[int]] = None
    applies_to: str = "all"
    category_id: Optional[UUID] = None
    item_id: Optional[UUID] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Offer name cannot be empty")
        return v.strip()

    @field_validator("offer_type")
    @classmethod
    def offer_type_valid(cls, v: str) -> str:
        if v not in VALID_OFFER_TYPES:
            raise ValueError(f"offer_type must be one of {VALID_OFFER_TYPES}")
        return v

    @field_validator("applies_to")
    @classmethod
    def applies_to_valid(cls, v: str) -> str:
        if v not in VALID_APPLIES_TO:
            raise ValueError(f"applies_to must be one of {VALID_APPLIES_TO}")
        return v

    @field_validator("discount_value")
    @classmethod
    def discount_value_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("discount_value must be greater than 0")
        return v

    @field_validator("days_of_week")
    @classmethod
    def days_valid(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        if v is not None:
            if not v:
                raise ValueError("days_of_week cannot be an empty list")
            if any(d < 0 or d > 6 for d in v):
                raise ValueError("days_of_week values must be between 0 (Sun) and 6 (Sat)")
        return v

    @model_validator(mode="after")
    def check_consistency(self):
        if self.offer_type == "percentage" and self.discount_value > 100:
            raise ValueError("percentage discount_value cannot exceed 100")
        if self.applies_to == "category" and not self.category_id:
            raise ValueError("category_id is required when applies_to='category'")
        if self.applies_to == "item" and not self.item_id:
            raise ValueError("item_id is required when applies_to='item'")
        if self.offer_type == "happy_hour" and (not self.start_time or not self.end_time):
            raise ValueError("happy_hour offers require start_time and end_time")
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class OfferUpdate(BaseModel):
    name: Optional[str] = None
    discount_value: Optional[Decimal] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    days_of_week: Optional[list[int]] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Offer name cannot be empty")
        return v.strip() if v else v

    @field_validator("discount_value")
    @classmethod
    def discount_value_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("discount_value must be greater than 0")
        return v


class ApplyOfferRequest(BaseModel):
    offer_id: UUID