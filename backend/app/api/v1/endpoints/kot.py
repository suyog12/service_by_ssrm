from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from uuid import UUID

from app.core.dependencies import get_current_user, get_current_admin
from app.core.database import get_tenant_db
from app.schemas.kot import KOTResponse, KOTAssign
from app.services import kot_service

router = APIRouter(tags=["KOT"])


@router.post(
    "/orders/{order_id}/kot",
    response_model=list[KOTResponse],
    status_code=201
)
async def generate_kots(
    order_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await kot_service.generate_kots_for_order(
            db, schema, outlet_id, order_id
        )


@router.get("/orders/{order_id}/kot", response_model=list[KOTResponse])
async def get_order_kots(
    order_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await kot_service.get_order_kots(
            db, schema, outlet_id, order_id
        )


@router.get("/kots/pending", response_model=list[dict])
async def get_pending_kots(
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await kot_service.get_pending_kots(db, schema, outlet_id)


@router.patch("/kots/{kot_id}/assign", response_model=KOTResponse)
async def assign_kot(
    kot_id: UUID,
    body: KOTAssign,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await kot_service.assign_kot(
            db, schema, outlet_id, kot_id, body.assigned_to
        )


@router.patch("/kots/{kot_id}/print", response_model=KOTResponse)
async def mark_printed(
    kot_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await kot_service.mark_kot_printed(
            db, schema, outlet_id, kot_id
        )


@router.get("/kots/{kot_id}/html", response_class=HTMLResponse)
async def get_kot_html(
    kot_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await kot_service.get_kot_html(
            db, schema, outlet_id, kot_id
        )