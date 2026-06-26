from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal


class LoyaltySettingsUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    points_per_amount: Optional[Decimal] = Field(default=None, gt=0)
    amount_per_point: Optional[Decimal] = Field(default=None, gt=0)
    redemption_rate: Optional[Decimal] = Field(default=None, gt=0)
    points_expiry_days: Optional[int] = Field(default=None, gt=0)
    min_redemption_pts: Optional[int] = Field(default=None, ge=0)


class EnrollCustomerRequest(BaseModel):
    customer_id: UUID


class RedeemPointsRequest(BaseModel):
    points_to_redeem: int = Field(..., gt=0)