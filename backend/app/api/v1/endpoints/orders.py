from fastapi import APIRouter, Depends, Query
from typing import Optional
from uuid import UUID

from app.core.dependencies import get_current_user, get_current_admin
from app.core.database import get_tenant_db
from app.schemas.order import (
    OrderCreate, OrderResponse, OrderStatusUpdate,
    OrderItemAdd, OrderItemResponse, OrderItemStatusUpdate,
)
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    body: OrderCreate,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await order_service.create_order(
            db, schema, outlet_id, body.model_dump(), current_user["user_id"]
        )


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    status: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await order_service.list_orders(db, schema, outlet_id, status)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await order_service.get_order(
            db, schema, outlet_id, order_id
        )


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: UUID,
    body: OrderStatusUpdate,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await order_service.update_order_status(
            db, schema, outlet_id, order_id,
            body.status.value, current_user["user_id"]
        )


@router.post(
    "/{order_id}/items",
    response_model=OrderItemResponse,
    status_code=201
)
async def add_item_to_order(
    order_id: UUID,
    body: OrderItemAdd,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await order_service.add_item_to_order(
            db, schema, outlet_id, order_id, body.model_dump()
        )


@router.get(
    "/{order_id}/items",
    response_model=list[OrderItemResponse]
)
async def list_order_items(
    order_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await order_service.list_order_items(
            db, schema, outlet_id, order_id
        )


@router.patch(
    "/{order_id}/items/{item_id}/status",
    response_model=OrderItemResponse
)
async def update_item_status(
    order_id: UUID,
    item_id: UUID,
    body: OrderItemStatusUpdate,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await order_service.update_item_status(
            db, schema, outlet_id, order_id,
            item_id, body.status.value
        )


@router.delete("/{order_id}/items/{item_id}")
async def cancel_order_item(
    order_id: UUID,
    item_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        await order_service.cancel_order_item(
            db, schema, outlet_id, order_id, item_id
        )
        return {"message": "Item cancelled"}