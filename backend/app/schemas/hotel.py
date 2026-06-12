from pydantic import BaseModel, Field
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal


# Room Type Schemas 

class RoomTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    base_price: Decimal = Field(..., gt=0)
    capacity: int = Field(default=2, ge=1)
    max_adults: int = Field(default=2, ge=1)
    max_children: int = Field(default=0, ge=0)
    bed_type: Optional[str] = Field(default=None)
    floor_area_sqm: Optional[Decimal] = None
    view_type: Optional[str] = Field(default="none")
    amenities: Optional[Any] = None
    image_urls: Optional[List[str]] = None


class RoomTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    base_price: Optional[Decimal] = Field(default=None, gt=0)
    capacity: Optional[int] = Field(default=None, ge=1)
    max_adults: Optional[int] = Field(default=None, ge=1)
    max_children: Optional[int] = Field(default=None, ge=0)
    bed_type: Optional[str] = None
    floor_area_sqm: Optional[Decimal] = None
    view_type: Optional[str] = None
    amenities: Optional[Any] = None
    image_urls: Optional[List[str]] = None
    is_active: Optional[bool] = None


class RoomTypeResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    base_price: Decimal
    capacity: int
    max_adults: int
    max_children: int
    bed_type: Optional[str]
    floor_area_sqm: Optional[Decimal]
    view_type: Optional[str]
    amenities: Optional[Any]
    image_urls: Optional[List[str]]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Pricing Rule Schemas 

class PricingRuleCreate(BaseModel):
    name: Optional[str] = None
    price: Decimal = Field(..., gt=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    days_of_week: Optional[List[int]] = None
    is_active: bool = True


class PricingRuleResponse(BaseModel):
    id: UUID
    room_type_id: UUID
    name: Optional[str]
    price: Decimal
    start_date: Optional[date]
    end_date: Optional[date]
    days_of_week: Optional[List[int]]
    is_active: bool
    created_at: datetime


# Room Schemas 

class RoomCreate(BaseModel):
    room_type_id: UUID
    room_number: str = Field(..., min_length=1, max_length=20)
    floor: Optional[str] = None
    notes: Optional[str] = None


class RoomUpdate(BaseModel):
    room_type_id: Optional[UUID] = None
    floor: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class RoomResponse(BaseModel):
    id: UUID
    room_type_id: UUID
    room_number: str
    floor: Optional[str]
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# Guest Schemas 

class GuestCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = None
    email: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    nationality: Optional[str] = None
    company_name: Optional[str] = None
    company_pan: Optional[str] = None
    is_corporate: bool = False


class GuestUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    phone: Optional[str] = None
    email: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    nationality: Optional[str] = None
    company_name: Optional[str] = None
    company_pan: Optional[str] = None
    is_corporate: Optional[bool] = None


class GuestResponse(BaseModel):
    id: UUID
    customer_id: Optional[UUID]
    full_name: str
    phone: Optional[str]
    email: Optional[str]
    id_type: Optional[str]
    id_number: Optional[str]
    nationality: Optional[str]
    company_name: Optional[str]
    company_pan: Optional[str]
    is_corporate: bool
    created_at: datetime
    updated_at: datetime


# Reservation Schemas 

class ReservationCreate(BaseModel):
    room_id: UUID
    guest_id: UUID
    check_in_date: date
    check_out_date: date
    adults: int = Field(default=1, ge=1)
    children: int = Field(default=0, ge=0)
    rate_per_night: Decimal = Field(..., gt=0)
    advance_deposit: Decimal = Field(default=Decimal("0"), ge=0)
    booking_source: str = Field(default="phone")
    booking_reference: Optional[str] = None
    commission_pct: Decimal = Field(default=Decimal("0"), ge=0)
    meal_plan: str = Field(default="room_only")
    special_requests: Optional[str] = None
    notes: Optional[str] = None


class ReservationUpdate(BaseModel):
    adults: Optional[int] = Field(default=None, ge=1)
    children: Optional[int] = Field(default=None, ge=0)
    rate_per_night: Optional[Decimal] = Field(default=None, gt=0)
    advance_deposit: Optional[Decimal] = Field(default=None, ge=0)
    booking_source: Optional[str] = None
    booking_reference: Optional[str] = None
    commission_pct: Optional[Decimal] = Field(default=None, ge=0)
    meal_plan: Optional[str] = None
    special_requests: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class ReservationResponse(BaseModel):
    id: UUID
    room_id: UUID
    guest_id: UUID
    check_in_date: date
    check_out_date: date
    actual_check_in: Optional[datetime]
    actual_check_out: Optional[datetime]
    adults: int
    children: int
    status: str
    rate_per_night: Decimal
    advance_deposit: Decimal
    booking_source: str
    booking_reference: Optional[str]
    commission_pct: Decimal
    meal_plan: str
    total_nights: Optional[int]
    total_amount: Decimal
    special_requests: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# Availability Schemas 

class AvailabilityResponse(BaseModel):
    room_type_id: UUID
    name: str
    description: Optional[str]
    base_price: Decimal
    price_for_stay: Decimal
    total_nights: int
    max_adults: int
    max_children: int
    bed_type: Optional[str]
    view_type: Optional[str]
    amenities: Optional[Any]
    image_urls: Optional[List[str]]
    available_rooms: int
    rooms: List[RoomResponse]


# Check In/Out Schemas 

class CheckInRequest(BaseModel):
    reservation_id: UUID
    room_id: Optional[UUID] = None


class CheckOutRequest(BaseModel):
    reservation_id: UUID


# Room Share Card Schema 

class RoomShareCard(BaseModel):
    room_type_id: UUID
    name: str
    description: Optional[str]
    base_price: Decimal
    max_adults: int
    max_children: int
    bed_type: Optional[str]
    floor_area_sqm: Optional[Decimal]
    view_type: Optional[str]
    amenities: Optional[Any]
    image_urls: Optional[List[str]]
    available_from: Optional[date]
    available_to: Optional[date]
    available_count: int