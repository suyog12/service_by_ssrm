from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class SubscriptionUsage(BaseModel):
    outlets: dict
    staff: dict
    menu_items: dict


class SubscriptionPlanOut(BaseModel):
    plan_code: str
    display_name: str
    price_monthly_npr: Optional[float]
    price_annual_npr: Optional[float]
    max_outlets: Optional[int]
    max_staff: Optional[int]
    max_menu_items: Optional[int]


class SubscriptionOut(BaseModel):
    status: str
    tier: str
    plan: Optional[SubscriptionPlanOut]
    is_demo: bool
    trial_ends_at: Optional[datetime]
    trial_days_remaining: Optional[int]
    demo_ends_at: Optional[datetime]
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    grace_period_ends_at: Optional[datetime]
    grace_period_days_remaining: Optional[int]
    cancelled_at: Optional[datetime]
    suspended_at: Optional[datetime]
    usage: SubscriptionUsage


class SubscriptionEventOut(BaseModel):
    id: UUID
    event_type: str
    from_status: Optional[str]
    to_status: Optional[str]
    from_tier: Optional[str]
    to_tier: Optional[str]
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    amount_npr: Optional[float]
    payment_reference: Optional[str]
    notes: Optional[str]
    created_by: str
    created_at: datetime


class RenewInfoOut(BaseModel):
    plan_code: str
    plan_display_name: str
    price_monthly_npr: Optional[float]
    qr_image_url: str
    payment_instructions: str
    reference_format: str


class PaymentReceiptIn(BaseModel):
    plan_code: str
    amount_npr: float
    payment_reference: str
    receipt_key: str      # R2 object key — uploaded via presigned URL first
    receipt_url: str      # R2 public URL


class PaymentReceiptOut(BaseModel):
    id: UUID
    plan_code: str
    amount_npr: float
    payment_reference: str
    receipt_url: str
    status: str
    created_at: datetime