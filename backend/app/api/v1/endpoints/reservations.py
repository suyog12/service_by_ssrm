from fastapi import APIRouter, Depends, Query
from typing import Optional
from uuid import UUID

from app.core.dependencies import require_feature
from app.core.database import get_tenant_db
from app.schemas.reservation import (
    ReservationCreate, ReservationUpdate, ReservationResponse,
)
from app.services import reservation_service

router = APIRouter(tags=["Floor Reservations"])


@router.post("/floor/reservations", response_model=ReservationResponse, status_code=201)
async def create_reservation(
    body: ReservationCreate,
    current_user: dict = Depends(require_feature("floor.reservations", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await reservation_service.create_reservation(
            db, schema, outlet_id, current_user["user_id"], body.model_dump()
        )


@router.get("/floor/reservations", response_model=list[ReservationResponse])
async def list_reservations(
    status: Optional[str] = Query(None),
    current_user: dict = Depends(require_feature("floor.reservations", "view")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await reservation_service.list_reservations(
            db, schema, outlet_id, status
        )


@router.get("/floor/reservations/{reservation_id}", response_model=ReservationResponse)
async def get_reservation(
    reservation_id: UUID,
    current_user: dict = Depends(require_feature("floor.reservations", "view")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await reservation_service.get_reservation(
            db, schema, outlet_id, reservation_id
        )


@router.patch("/floor/reservations/{reservation_id}", response_model=ReservationResponse)
async def update_reservation(
    reservation_id: UUID,
    body: ReservationUpdate,
    current_user: dict = Depends(require_feature("floor.reservations", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        return await reservation_service.update_reservation(
            db, schema, outlet_id, reservation_id, data
        )


@router.post("/floor/reservations/{reservation_id}/seat", response_model=ReservationResponse)
async def seat_reservation(
    reservation_id: UUID,
    current_user: dict = Depends(require_feature("floor.reservations", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await reservation_service.seat_reservation(
            db, schema, outlet_id, reservation_id
        )