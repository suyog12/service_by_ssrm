from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import date, time
from decimal import Decimal


class ShiftCreate(BaseModel):
    name: str = Field(..., min_length=1)
    start_time: time
    end_time: time


class ShiftUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_active: Optional[bool] = None


class HRSettingsUpdate(BaseModel):
    work_hours_per_day: Optional[Decimal] = Field(default=None, gt=0)
    overtime_multiplier: Optional[Decimal] = Field(default=None, gt=0)
    late_threshold_minutes: Optional[int] = Field(default=None, ge=0)
    scheme: Optional[str] = Field(default=None, pattern="^(pf|ssf|both)$")
    pf_employee_pct: Optional[Decimal] = Field(default=None, ge=0)
    pf_employer_pct: Optional[Decimal] = Field(default=None, ge=0)
    cit_employee_pct: Optional[Decimal] = Field(default=None, ge=0)
    cit_employer_pct: Optional[Decimal] = Field(default=None, ge=0)
    ssf_employee_pct: Optional[Decimal] = Field(default=None, ge=0)
    ssf_employer_pct: Optional[Decimal] = Field(default=None, ge=0)


class TaxSlabCreate(BaseModel):
    fiscal_year: str = Field(..., min_length=1)
    basic_exemption: Decimal = Field(default=Decimal("500000"), ge=0)
    slabs: list[dict]


class AttendanceCheckIn(BaseModel):
    shift_id: Optional[UUID] = None
    check_in_lat: Optional[Decimal] = None
    check_in_lng: Optional[Decimal] = None
    notes: Optional[str] = None


class AttendanceCheckOut(BaseModel):
    check_out_lat: Optional[Decimal] = None
    check_out_lng: Optional[Decimal] = None


class AttendanceOverride(BaseModel):
    user_id: UUID
    status: str = Field(..., pattern="^(present|absent|half_day|leave)$")
    shift_id: Optional[UUID] = None
    notes: Optional[str] = None
    attendance_date: date


class LeaveTypeCreate(BaseModel):
    name: str = Field(..., min_length=1)
    days_allowed: Optional[int] = Field(default=None, gt=0)
    is_paid: bool = True


class LeaveTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    days_allowed: Optional[int] = Field(default=None, gt=0)
    is_paid: Optional[bool] = None


class LeaveRequestCreate(BaseModel):
    leave_type_id: UUID
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveReview(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$")


class PayrollPeriodCreate(BaseModel):
    period_name: str = Field(..., min_length=1)
    start_date: date
    end_date: date


class PayrollEntryUpdate(BaseModel):
    bonuses: Optional[Decimal] = Field(default=None, ge=0)
    deductions: Optional[Decimal] = Field(default=None, ge=0)
    notes: Optional[str] = None


class ShiftHandoverCreate(BaseModel):
    incoming_user_id: UUID
    shift_id: Optional[UUID] = None
    notes: Optional[str] = None
    cash_amount: Optional[Decimal] = Field(default=None, ge=0)
    incidents: Optional[str] = None