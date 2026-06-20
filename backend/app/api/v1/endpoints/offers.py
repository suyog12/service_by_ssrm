from fastapi import APIRouter, Depends, Query
from typing import Optional
from uuid import UUID

from app.core.dependencies import require_feature
from app.core.database import get_tenant_db
from app.schemas.offer import OfferCreate, OfferUpdate, ApplyOfferRequest
from app.schemas.billing import BillResponse
from app.services import offer_service

router = APIRouter(tags=["Menu Offers"])


@router.post("/menu/offers", status_code=201)
async def create_offer(
    body: OfferCreate,
    current_user: dict = Depends(require_feature("menu.offers", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await offer_service.create_offer(
            db, schema, outlet_id, body.model_dump(), current_user["user_id"]
        )


@router.get("/menu/offers")
async def list_offers(
    active_only: bool = Query(default=False),
    current_user: dict = Depends(require_feature("menu.offers", "view")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await offer_service.list_offers(db, schema, outlet_id, active_only)


@router.get("/menu/offers/eligible")
async def list_eligible_offers(
    current_user: dict = Depends(require_feature("menu.offers", "view")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await offer_service.list_eligible_offers(db, schema, outlet_id)


@router.get("/menu/offers/{offer_id}")
async def get_offer(
    offer_id: UUID,
    current_user: dict = Depends(require_feature("menu.offers", "view")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await offer_service.get_offer(db, schema, outlet_id, offer_id)


@router.patch("/menu/offers/{offer_id}")
async def update_offer(
    offer_id: UUID,
    body: OfferUpdate,
    current_user: dict = Depends(require_feature("menu.offers", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        return await offer_service.update_offer(db, schema, outlet_id, offer_id, data)


@router.delete("/menu/offers/{offer_id}")
async def delete_offer(
    offer_id: UUID,
    current_user: dict = Depends(require_feature("menu.offers", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await offer_service.delete_offer(db, schema, outlet_id, offer_id)


@router.post("/billing/bills/{bill_id}/offers", response_model=BillResponse)
async def apply_offer_to_bill(
    bill_id: UUID,
    body: ApplyOfferRequest,
    current_user: dict = Depends(require_feature("billing.discount", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await offer_service.apply_offer(
            db, schema, outlet_id, bill_id, body.offer_id, current_user["user_id"]
        )


@router.get("/billing/bills/{bill_id}/offers")
async def list_bill_offers(
    bill_id: UUID,
    current_user: dict = Depends(require_feature("billing.view", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await offer_service.list_bill_offers(db, schema, bill_id)


@router.delete("/billing/bills/{bill_id}/offers/{offer_id}", response_model=BillResponse)
async def remove_offer_from_bill(
    bill_id: UUID,
    offer_id: UUID,
    current_user: dict = Depends(require_feature("billing.discount", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await offer_service.remove_offer(db, schema, outlet_id, bill_id, offer_id)