from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from uuid import UUID
from datetime import date
from decimal import Decimal

from app.core.dependencies import get_current_user, get_db, require_admin
from app.schemas.hotel import (
    RoomTypeCreate, RoomTypeUpdate, RoomTypeResponse,
    PricingRuleCreate, PricingRuleResponse,
    RoomCreate, RoomUpdate, RoomResponse,
    GuestCreate, GuestUpdate, GuestResponse,
    ReservationCreate, ReservationUpdate, ReservationResponse,
    AvailabilityResponse, RoomShareCard,
)
from app.services import hotel_service

router = APIRouter(prefix="/hotel", tags=["hotel"])


# Room Types 

@router.post("/room-types", status_code=201)
async def create_room_type(
    data: RoomTypeCreate,
    current_user=Depends(require_admin),
    db=Depends(get_db)
):
    return await hotel_service.create_room_type(
        data, current_user["schema_name"], db
    )


@router.get("/room-types")
async def list_room_types(
    active_only: bool = Query(default=True),
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.list_room_types(
        current_user["schema_name"], db, active_only
    )


@router.get("/room-types/{room_type_id}")
async def get_room_type(
    room_type_id: UUID,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.get_room_type(
        room_type_id, current_user["schema_name"], db
    )


@router.patch("/room-types/{room_type_id}")
async def update_room_type(
    room_type_id: UUID,
    data: RoomTypeUpdate,
    current_user=Depends(require_admin),
    db=Depends(get_db)
):
    return await hotel_service.update_room_type(
        room_type_id, data, current_user["schema_name"], db
    )


@router.delete("/room-types/{room_type_id}")
async def delete_room_type(
    room_type_id: UUID,
    current_user=Depends(require_admin),
    db=Depends(get_db)
):
    return await hotel_service.delete_room_type(
        room_type_id, current_user["schema_name"], db
    )


@router.get("/room-types/{room_type_id}/share-card")
async def get_share_card(
    room_type_id: UUID,
    check_in: Optional[date] = Query(default=None),
    check_out: Optional[date] = Query(default=None),
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.get_room_share_card(
        room_type_id, current_user["schema_name"], db, check_in, check_out
    )


# Pricing Rules 

@router.post("/room-types/{room_type_id}/pricing-rules", status_code=201)
async def create_pricing_rule(
    room_type_id: UUID,
    data: PricingRuleCreate,
    current_user=Depends(require_admin),
    db=Depends(get_db)
):
    return await hotel_service.create_pricing_rule(
        room_type_id, data, current_user["schema_name"], db
    )


@router.get("/room-types/{room_type_id}/pricing-rules")
async def list_pricing_rules(
    room_type_id: UUID,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.list_pricing_rules(
        room_type_id, current_user["schema_name"], db
    )


@router.delete("/pricing-rules/{rule_id}")
async def delete_pricing_rule(
    rule_id: UUID,
    current_user=Depends(require_admin),
    db=Depends(get_db)
):
    return await hotel_service.delete_pricing_rule(
        rule_id, current_user["schema_name"], db
    )


# Rooms 

@router.post("/rooms", status_code=201)
async def create_room(
    data: RoomCreate,
    current_user=Depends(require_admin),
    db=Depends(get_db)
):
    return await hotel_service.create_room(
        data, current_user["schema_name"], db
    )


@router.get("/rooms")
async def list_rooms(
    room_type_id: Optional[UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.list_rooms(
        current_user["schema_name"], db, room_type_id, status
    )


@router.get("/rooms/availability")
async def check_availability(
    check_in: date = Query(...),
    check_out: date = Query(...),
    adults: int = Query(default=1, ge=1),
    children: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.check_availability(
        check_in, check_out, adults, children,
        current_user["schema_name"], db
    )


@router.get("/rooms/{room_id}")
async def get_room(
    room_id: UUID,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.get_room(
        room_id, current_user["schema_name"], db
    )


@router.patch("/rooms/{room_id}")
async def update_room(
    room_id: UUID,
    data: RoomUpdate,
    current_user=Depends(require_admin),
    db=Depends(get_db)
):
    return await hotel_service.update_room(
        room_id, data, current_user["schema_name"], db
    )


@router.delete("/rooms/{room_id}")
async def delete_room(
    room_id: UUID,
    current_user=Depends(require_admin),
    db=Depends(get_db)
):
    return await hotel_service.delete_room(
        room_id, current_user["schema_name"], db
    )


# Guests 

@router.post("/guests", status_code=201)
async def create_guest(
    data: GuestCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.create_guest(
        data, current_user["schema_name"], db
    )


@router.get("/guests")
async def list_guests(
    search: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.list_guests(
        current_user["schema_name"], db, search
    )


@router.get("/guests/{guest_id}")
async def get_guest(
    guest_id: UUID,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.get_guest(
        guest_id, current_user["schema_name"], db
    )


@router.patch("/guests/{guest_id}")
async def update_guest(
    guest_id: UUID,
    data: GuestUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.update_guest(
        guest_id, data, current_user["schema_name"], db
    )


# Reservations 

@router.post("/reservations", status_code=201)
async def create_reservation(
    data: ReservationCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.create_reservation(
        data, current_user["schema_name"], db, current_user["user_id"]
    )


@router.get("/reservations")
async def list_reservations(
    status: Optional[str] = Query(default=None),
    guest_id: Optional[UUID] = Query(default=None),
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.list_reservations(
        current_user["schema_name"], db, status, guest_id
    )


@router.get("/reservations/{reservation_id}")
async def get_reservation(
    reservation_id: UUID,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.get_reservation(
        reservation_id, current_user["schema_name"], db
    )


@router.patch("/reservations/{reservation_id}")
async def update_reservation(
    reservation_id: UUID,
    data: ReservationUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.update_reservation(
        reservation_id, data, current_user["schema_name"], db
    )


@router.post("/reservations/{reservation_id}/cancel")
async def cancel_reservation(
    reservation_id: UUID,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.cancel_reservation(
        reservation_id, current_user["schema_name"], db
    )


# Check In / Check Out 

@router.post("/reservations/{reservation_id}/check-in")
async def check_in(
    reservation_id: UUID,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.check_in(
        reservation_id, current_user["schema_name"], db
    )


@router.post("/reservations/{reservation_id}/check-out")
async def check_out(
    reservation_id: UUID,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.check_out(
        reservation_id, current_user["schema_name"], db
    )


# Guest Folio 

@router.get("/reservations/{reservation_id}/folio")
async def get_folio(
    reservation_id: UUID,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.get_folio(
        reservation_id, current_user["schema_name"], db
    )


@router.post("/reservations/{reservation_id}/folio/charges", status_code=201)
async def add_folio_charge(
    reservation_id: UUID,
    charge_type: str,
    description: str,
    amount: Decimal,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    return await hotel_service.add_folio_charge(
        reservation_id, charge_type, description, amount,
        current_user["schema_name"], db, current_user["user_id"]
    )