from fastapi import APIRouter, Depends, Query
from typing import Optional
from uuid import UUID

from app.core.dependencies import require_feature
from app.core.database import get_tenant_db
from app.schemas.floor import (
    SectionCreate, SectionUpdate, SectionResponse,
    TableCreate, TableUpdate, TableResponse,
)
from app.services import floor_service

router = APIRouter(tags=["Floor Management"])


# Sections

@router.post("/floor/sections", response_model=SectionResponse, status_code=201)
async def create_section(
    body: SectionCreate,
    current_user: dict = Depends(require_feature("floor.tables", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await floor_service.create_section(
            db, schema, outlet_id, body.model_dump()
        )


@router.get("/floor/sections", response_model=list[SectionResponse])
async def list_sections(
    current_user: dict = Depends(require_feature("floor.tables", "view")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await floor_service.list_sections(db, schema, outlet_id)


@router.patch("/floor/sections/{section_id}", response_model=SectionResponse)
async def update_section(
    section_id: UUID,
    body: SectionUpdate,
    current_user: dict = Depends(require_feature("floor.tables", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        return await floor_service.update_section(
            db, schema, outlet_id, section_id, data
        )


@router.delete("/floor/sections/{section_id}")
async def delete_section(
    section_id: UUID,
    current_user: dict = Depends(require_feature("floor.tables", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        await floor_service.delete_section(
            db, schema, outlet_id, section_id
        )
        return {"message": "Section deleted successfully"}


# Tables

@router.post("/floor/tables", response_model=TableResponse, status_code=201)
async def create_table(
    body: TableCreate,
    current_user: dict = Depends(require_feature("floor.tables", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await floor_service.create_table(
            db, schema, outlet_id, body.model_dump()
        )


@router.get("/floor/tables", response_model=list[TableResponse])
async def list_tables(
    section_id: Optional[UUID] = Query(None),
    current_user: dict = Depends(require_feature("floor.tables", "view")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await floor_service.list_tables(
            db, schema, outlet_id, section_id
        )


@router.get("/floor/tables/{table_id}", response_model=TableResponse)
async def get_table(
    table_id: UUID,
    current_user: dict = Depends(require_feature("floor.tables", "view")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await floor_service.get_table(
            db, schema, outlet_id, table_id
        )


@router.patch("/floor/tables/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: UUID,
    body: TableUpdate,
    current_user: dict = Depends(require_feature("floor.tables", "view")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        return await floor_service.update_table(
            db, schema, outlet_id, table_id, data
        )


@router.delete("/floor/tables/{table_id}")
async def delete_table(
    table_id: UUID,
    current_user: dict = Depends(require_feature("floor.tables", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        await floor_service.delete_table(
            db, schema, outlet_id, table_id
        )
        return {"message": "Table deleted successfully"}