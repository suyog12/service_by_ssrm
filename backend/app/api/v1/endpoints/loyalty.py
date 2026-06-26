from fastapi import APIRouter, Depends
from uuid import UUID

from app.core.dependencies import require_feature
from app.core.database import get_tenant_db
from app.schemas.loyalty import (
    LoyaltySettingsUpdate, EnrollCustomerRequest, RedeemPointsRequest
)
from app.schemas.billing import BillResponse
from app.services import loyalty_service

router = APIRouter(tags=["Loyalty"])


@router.get("/loyalty/settings")
async def get_settings(
    current_user: dict = Depends(require_feature("menu.offers", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await loyalty_service.get_settings(db, schema)


@router.patch("/loyalty/settings")
async def update_settings(
    body: LoyaltySettingsUpdate,
    current_user: dict = Depends(require_feature("menu.offers", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        return await loyalty_service.update_settings(db, schema, data)


@router.post("/loyalty/customers/{customer_id}/enroll", status_code=201)
async def enroll_customer(
    customer_id: UUID,
    current_user: dict = Depends(require_feature("menu.offers", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await loyalty_service.enroll_customer(db, schema, customer_id)


@router.get("/loyalty/customers/{customer_id}")
async def get_account(
    customer_id: UUID,
    current_user: dict = Depends(require_feature("menu.offers", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await loyalty_service.get_account(db, schema, customer_id)


@router.get("/loyalty/customers/{customer_id}/transactions")
async def list_transactions(
    customer_id: UUID,
    current_user: dict = Depends(require_feature("menu.offers", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await loyalty_service.list_transactions(db, schema, customer_id)


@router.post("/billing/bills/{bill_id}/loyalty/redeem", response_model=BillResponse)
async def redeem_points(
    bill_id: UUID,
    body: RedeemPointsRequest,
    current_user: dict = Depends(require_feature("billing.discount", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await loyalty_service.redeem_points_on_bill(
            db, schema, outlet_id, bill_id, body.points_to_redeem
        )