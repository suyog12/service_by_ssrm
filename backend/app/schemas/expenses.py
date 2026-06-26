from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import date
from decimal import Decimal


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    is_petty: bool = False


class ExpenseCategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    is_petty: Optional[bool] = None


class ExpenseLogCreate(BaseModel):
    category_id: UUID
    amount: Decimal = Field(..., gt=0)
    description: str = Field(..., min_length=1)
    expense_date: date
    outlet_id: Optional[UUID] = None
    receipt_url: Optional[str] = None
    is_petty: bool = False
    supplier_id: Optional[UUID] = None
    po_id: Optional[UUID] = None


class CashRegisterAction(BaseModel):
    action: str = Field(..., pattern="^(open|close)$")
    cash_amount: Decimal = Field(..., ge=0)
    shift_id: Optional[UUID] = None
    notes: Optional[str] = None