from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from typing import Optional
from uuid import UUID

from app.core.dependencies import get_current_user, get_current_admin
from app.core.database import get_tenant_db
from app.schemas.billing import (
    BillingSettingsUpdate, BillingSettingsResponse,
    BillCreate, BillResponse, DiscountApply,
    PaymentCreate, PaymentResponse,
    CreditAccountCreate, CreditAccountUpdate, CreditAccountResponse,
    CreditSettlement,
)
from app.services import billing_service

router = APIRouter(tags=["Billing"])


# Billing Settings 

@router.get("/billing/settings", response_model=BillingSettingsResponse)
async def get_billing_settings(
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.get_or_create_billing_settings(db, schema)


@router.patch("/billing/settings", response_model=BillingSettingsResponse)
async def update_billing_settings(
    body: BillingSettingsUpdate,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.update_billing_settings(
            db, schema, body.model_dump(exclude_none=True)
        )


# Bills 

@router.post("/billing/bills", response_model=BillResponse, status_code=201)
async def generate_bill(
    body: BillCreate,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.generate_bill(
            db, schema, body.model_dump(), current_user["user_id"]
        )


@router.get("/billing/bills", response_model=list[dict])
async def list_bills(
    status: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.list_bills(db, schema, status)


@router.get("/billing/bills/{bill_id}", response_model=BillResponse)
async def get_bill(
    bill_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.get_bill(db, schema, bill_id)


@router.post("/billing/bills/{bill_id}/discount", response_model=BillResponse)
async def apply_discount(
    bill_id: UUID,
    body: DiscountApply,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.apply_discount(
            db, schema, bill_id, body.model_dump(), current_user["user_id"]
        )


@router.post("/billing/bills/{bill_id}/payment", response_model=BillResponse)
async def process_payment(
    bill_id: UUID,
    body: PaymentCreate,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.process_payment(
            db, schema, bill_id, body.model_dump(), current_user["user_id"]
        )


@router.post("/billing/bills/{bill_id}/void", response_model=BillResponse)
async def void_bill(
    bill_id: UUID,
    reason: str = Query(...),
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.void_bill(
            db, schema, bill_id, reason, current_user["user_id"]
        )


@router.get("/billing/bills/{bill_id}/html", response_class=HTMLResponse)
async def get_bill_html(
    bill_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.get_bill_html(db, schema, bill_id)


# Credit Accounts 

@router.post("/billing/credit-accounts", response_model=CreditAccountResponse, status_code=201)
async def create_credit_account(
    body: CreditAccountCreate,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.create_credit_account(
            db, schema, body.model_dump()
        )


@router.get("/billing/credit-accounts", response_model=list[CreditAccountResponse])
async def list_credit_accounts(
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.list_credit_accounts(db, schema)


@router.get("/billing/credit-accounts/{account_id}", response_model=CreditAccountResponse)
async def get_credit_account(
    account_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.get_credit_account(db, schema, account_id)


@router.patch("/billing/credit-accounts/{account_id}", response_model=CreditAccountResponse)
async def update_credit_account(
    account_id: UUID,
    body: CreditAccountUpdate,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.update_credit_account(
            db, schema, account_id,
            body.model_dump(exclude_none=True)
        )


@router.post("/billing/credit-accounts/{account_id}/settle", response_model=CreditAccountResponse)
async def settle_credit_account(
    account_id: UUID,
    body: CreditSettlement,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.settle_credit_account(
            db, schema, account_id, body.model_dump(), current_user["user_id"]
        )


@router.get("/billing/credit-accounts/{account_id}/statement", response_class=HTMLResponse)
async def get_credit_account_statement(
    account_id: UUID,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await billing_service.get_credit_account_statement_html(
            db, schema, account_id
        )