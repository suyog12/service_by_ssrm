from fastapi import APIRouter, Depends, Query
from uuid import UUID
from typing import Optional
from app.core.dependencies import get_db, get_current_user, require_admin
from app.schemas.inventory import (
    SupplierCreate, SupplierUpdate, SupplierResponse,
    StockAddRequest, StockAddResponse,
    StockAdjustRequest, StockAdjustResponse,
    ReorderAlertItem,
    POCreate, POItemAdd, POResponse, POReceiveItem,
)
from app.services import inventory_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


# Suppliers 

@router.post("/suppliers", status_code=201, response_model=SupplierResponse)
async def create_supplier(
    data: SupplierCreate,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await inventory_service.create_supplier(
        db, current_user["schema_name"], data.model_dump()
    )


@router.get("/suppliers", response_model=list[SupplierResponse])
async def list_suppliers(
    active_only: bool = Query(False),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await inventory_service.list_suppliers(
        db, current_user["schema_name"], active_only
    )


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: UUID,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await inventory_service.get_supplier(
        db, current_user["schema_name"], supplier_id
    )


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: UUID,
    data: SupplierUpdate,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await inventory_service.update_supplier(
        db, current_user["schema_name"], supplier_id,
        data.model_dump(exclude_none=True)
    )


# Stock 

@router.post("/stock/add", status_code=201, response_model=StockAddResponse)
async def add_stock(
    data: StockAddRequest,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await inventory_service.add_stock(
        db, current_user["schema_name"], data.model_dump()
    )


@router.post("/stock/adjust", status_code=201, response_model=StockAdjustResponse)
async def adjust_stock(
    data: StockAdjustRequest,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await inventory_service.adjust_stock(
        db, current_user["schema_name"], data.model_dump(),
        current_user["user_id"]
    )


@router.get("/stock/adjustments", response_model=list[StockAdjustResponse])
async def list_adjustments(
    ingredient_id: Optional[UUID] = Query(None),
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await inventory_service.list_stock_adjustments(
        db, current_user["schema_name"], ingredient_id
    )


@router.get("/stock/reorder-alerts", response_model=list[ReorderAlertItem])
async def reorder_alerts(
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await inventory_service.get_reorder_alerts(
        db, current_user["schema_name"]
    )


# Purchase Orders 

@router.post("/purchase-orders", status_code=201, response_model=POResponse)
async def create_purchase_order(
    data: POCreate,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await inventory_service.create_purchase_order(
        db, current_user["schema_name"], data.model_dump(),
        current_user["user_id"]
    )


@router.get("/purchase-orders", response_model=list[POResponse])
async def list_purchase_orders(
    status: Optional[str] = Query(None),
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await inventory_service.list_purchase_orders(
        db, current_user["schema_name"], status
    )


@router.get("/purchase-orders/{po_id}", response_model=POResponse)
async def get_purchase_order(
    po_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await inventory_service.get_purchase_order(
        db, current_user["schema_name"], po_id
    )


@router.post("/purchase-orders/{po_id}/items", response_model=POResponse)
async def add_po_item(
    po_id: UUID,
    data: POItemAdd,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await inventory_service.add_po_item(
        db, current_user["schema_name"], po_id, data.model_dump()
    )


@router.patch("/purchase-orders/{po_id}/status", response_model=POResponse)
async def update_po_status(
    po_id: UUID,
    status: str,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await inventory_service.update_po_status(
        db, current_user["schema_name"], po_id, status,
        current_user["user_id"]
    )


@router.post("/purchase-orders/{po_id}/receive", response_model=POResponse)
async def receive_purchase_order(
    po_id: UUID,
    items: list[POReceiveItem],
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await inventory_service.receive_purchase_order(
        db, current_user["schema_name"], po_id,
        [i.model_dump() for i in items],
        current_user["user_id"]
    )