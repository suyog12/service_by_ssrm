from fastapi import APIRouter, Depends
from uuid import UUID

from app.core.dependencies import get_current_user, get_current_admin
from app.core.database import get_tenant_db
from app.schemas.ingredient import (
    IngredientCreate, IngredientUpdate, IngredientResponse,
    ItemIngredientAdd, ItemIngredientUpdate, ItemIngredientResponse,
)
from app.services import ingredient_service

router = APIRouter(tags=["Ingredients"])


# Ingredients 

@router.post("/ingredients", response_model=IngredientResponse, status_code=201)
async def create_ingredient(
    body: IngredientCreate,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await ingredient_service.create_ingredient(
            db, schema, outlet_id, body.model_dump()
        )


@router.get("/ingredients", response_model=list[IngredientResponse])
async def list_ingredients(
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await ingredient_service.list_ingredients(
            db, schema, outlet_id
        )


@router.get("/ingredients/{ingredient_id}", response_model=IngredientResponse)
async def get_ingredient(
    ingredient_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await ingredient_service.get_ingredient(
            db, schema, outlet_id, ingredient_id
        )


@router.patch("/ingredients/{ingredient_id}", response_model=IngredientResponse)
async def update_ingredient(
    ingredient_id: UUID,
    body: IngredientUpdate,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        return await ingredient_service.update_ingredient(
            db, schema, outlet_id, ingredient_id, data
        )


@router.delete("/ingredients/{ingredient_id}")
async def delete_ingredient(
    ingredient_id: UUID,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        await ingredient_service.delete_ingredient(
            db, schema, outlet_id, ingredient_id
        )
        return {"message": "Ingredient deleted successfully"}


# Item ingredient linking 

@router.post(
    "/menu/items/{item_id}/ingredients",
    response_model=ItemIngredientResponse,
    status_code=201
)
async def add_ingredient_to_item(
    item_id: UUID,
    body: ItemIngredientAdd,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await ingredient_service.add_ingredient_to_item(
            db, schema, outlet_id, item_id, body.model_dump()
        )


@router.get(
    "/menu/items/{item_id}/ingredients",
    response_model=list[ItemIngredientResponse]
)
async def list_item_ingredients(
    item_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await ingredient_service.list_item_ingredients(
            db, schema, outlet_id, item_id
        )


@router.patch(
    "/menu/items/{item_id}/ingredients/{ingredient_id}",
    response_model=ItemIngredientResponse
)
async def update_item_ingredient(
    item_id: UUID,
    ingredient_id: UUID,
    body: ItemIngredientUpdate,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await ingredient_service.update_item_ingredient(
            db, schema, outlet_id, item_id, ingredient_id, body.model_dump()
        )


@router.delete("/menu/items/{item_id}/ingredients/{ingredient_id}")
async def remove_ingredient_from_item(
    item_id: UUID,
    ingredient_id: UUID,
    current_user: dict = Depends(get_current_admin),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        await ingredient_service.remove_ingredient_from_item(
            db, schema, outlet_id, item_id, ingredient_id
        )
        return {"message": "Ingredient removed from item"}