from fastapi import APIRouter, Depends, Query
from typing import Optional
from uuid import UUID

from app.core.dependencies import get_current_user, get_current_admin
from app.core.database import get_tenant_db
from app.schemas.menu import (
    CategoryCreate, CategoryUpdate, CategoryResponse,
    MenuItemCreate, MenuItemUpdate, MenuItemResponse,
)
from app.services import menu_service

router = APIRouter(prefix="/menu", tags=["Menu Management"])


# Categories 

@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(
    body: CategoryCreate,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await menu_service.create_category(
            db, schema, outlet_id, body.model_dump()
        )


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await menu_service.list_categories(db, schema, outlet_id)


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    body: CategoryUpdate,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        return await menu_service.update_category(
            db, schema, outlet_id, category_id, data
        )


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: UUID,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        await menu_service.delete_category(
            db, schema, outlet_id, category_id
        )
        return {"message": "Category deleted successfully"}


# Menu Items 

@router.post("/items", response_model=MenuItemResponse, status_code=201)
async def create_item(
    body: MenuItemCreate,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await menu_service.create_item(
            db, schema, outlet_id, body.model_dump()
        )


@router.get("/items", response_model=list[MenuItemResponse])
async def list_items(
    category_id: Optional[UUID] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await menu_service.list_items(
            db, schema, outlet_id, category_id
        )


@router.get("/items/{item_id}", response_model=MenuItemResponse)
async def get_item(
    item_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await menu_service.get_item(db, schema, outlet_id, item_id)


@router.patch("/items/{item_id}", response_model=MenuItemResponse)
async def update_item(
    item_id: UUID,
    body: MenuItemUpdate,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        return await menu_service.update_item(
            db, schema, outlet_id, item_id, data
        )


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: UUID,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        await menu_service.delete_item(db, schema, outlet_id, item_id)
        return {"message": "Menu item deleted successfully"}