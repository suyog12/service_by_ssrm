from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime


# Billing Settings 

class BillingSettingsUpdate(BaseModel):
    vat_mode: Optional[str] = None
    vat_pct: Optional[Decimal] = None
    service_charge_mode: Optional[str] = None
    service_charge_pct: Optional[Decimal] = None
    qr_type: Optional[str] = None
    qr_image_url: Optional[str] = None
    fonepay_merchant_id: Optional[str] = None

    @field_validator("vat_mode")
    @classmethod
    def vat_mode_valid(cls, v):
        if v is not None and v not in ("inclusive", "exclusive"):
            raise ValueError("vat_mode must be inclusive or exclusive")
        return v

    @field_validator("service_charge_mode")
    @classmethod
    def sc_mode_valid(cls, v):
        if v is not None and v not in ("inclusive", "exclusive"):
            raise ValueError("service_charge_mode must be inclusive or exclusive")
        return v

    @field_validator("qr_type")
    @classmethod
    def qr_type_valid(cls, v):
        if v is not None and v not in ("none", "custom", "fonepay"):
            raise ValueError("qr_type must be none, custom, or fonepay")
        return v


class BillingSettingsResponse(BaseModel):
    id: UUID
    vat_mode: str
    vat_pct: Decimal
    service_charge_mode: str
    service_charge_pct: Decimal
    qr_type: str
    qr_image_url: Optional[str] = None
    fonepay_merchant_id: Optional[str] = None

    class Config:
        from_attributes = True


# Bill 

class BillCreate(BaseModel):
    order_id: UUID
    customer_id: Optional[UUID] = None
    is_corporate: bool = False
    corporate_name: Optional[str] = None
    corporate_pan: Optional[str] = None
    credit_account_id: Optional[UUID] = None


class DiscountApply(BaseModel):
    discount_level: str
    discount_pct: Decimal
    category_id: Optional[UUID] = None
    order_item_id: Optional[UUID] = None

    @field_validator("discount_level")
    @classmethod
    def level_valid(cls, v):
        if v not in ("bill", "category", "item"):
            raise ValueError("discount_level must be bill, category, or item")
        return v

    @field_validator("discount_pct")
    @classmethod
    def pct_positive(cls, v):
        if v < 0 or v > 100:
            raise ValueError("discount_pct must be between 0 and 100")
        return v


class BillLineItem(BaseModel):
    order_item_id: UUID
    item_name: str
    quantity: int
    unit_price: Decimal
    discount_amt: Decimal
    line_total: Decimal


class BillResponse(BaseModel):
    id: UUID
    bill_number: str
    order_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    credit_account_id: Optional[UUID] = None
    is_corporate: bool
    corporate_name: Optional[str] = None
    corporate_pan: Optional[str] = None
    subtotal: Decimal
    service_charge_pct: Decimal
    service_charge_amt: Decimal
    vat_pct: Decimal
    vat_amt: Decimal
    discount_amt: Decimal
    total_amount: Decimal
    status: str
    items: list[BillLineItem] = []
    qr_type: Optional[str] = None
    qr_image_url: Optional[str] = None
    generated_by: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Payment 

class PaymentCreate(BaseModel):
    method: str
    amount: Decimal
    transaction_ref: Optional[str] = None

    @field_validator("method")
    @classmethod
    def method_valid(cls, v):
        valid = {"cash", "esewa", "khalti", "card", "fonepay",
                 "room_charge", "loyalty_points", "credit_account"}
        if v not in valid:
            raise ValueError(f"method must be one of {valid}")
        return v

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v


class PaymentResponse(BaseModel):
    id: UUID
    bill_id: UUID
    method: str
    amount: Decimal
    transaction_ref: Optional[str] = None
    status: str
    processed_at: datetime

    class Config:
        from_attributes = True


# Credit Accounts 

class CreditAccountCreate(BaseModel):
    account_type: str
    display_name: str
    customer_id: Optional[UUID] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_email: Optional[str] = None
    credit_limit: Decimal = Decimal("0")
    payment_terms: int = 30
    notes: Optional[str] = None

    @field_validator("account_type")
    @classmethod
    def type_valid(cls, v):
        if v not in ("individual", "corporate"):
            raise ValueError("account_type must be individual or corporate")
        return v

    @field_validator("display_name")
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("display_name cannot be empty")
        return v.strip()


class CreditAccountUpdate(BaseModel):
    display_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_email: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    payment_terms: Optional[int] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class CreditAccountResponse(BaseModel):
    id: UUID
    account_type: str
    display_name: str
    customer_id: Optional[UUID] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_email: Optional[str] = None
    credit_limit: Decimal
    current_balance: Decimal
    payment_terms: int
    is_active: bool
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class CreditSettlement(BaseModel):
    amount: Decimal
    reference: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v