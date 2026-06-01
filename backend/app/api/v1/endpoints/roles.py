from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import List
import asyncpg

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.schemas.role import (
    CreateRoleRequest, UpdateRoleRequest,
    RoleResponse, RoleListResponse, FeatureResponse
)
from app.services.role_service import (
    get_all_features,
    create_role,
    get_role,
    list_roles,
    update_role,
    delete_role
)

router = APIRouter(prefix="/roles", tags=["Roles & Permissions"])


@router.get("/features", response_model=List[FeatureResponse])
async def list_features(
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
):
    """List all available features that can be assigned to roles"""
    return await get_all_features(db)


@router.get("", response_model=List[RoleListResponse])
async def list_all_roles(
    current_user: dict = Depends(require_permission("config.roles", "view")),
    db: asyncpg.Connection = Depends(get_db)
):
    return await list_roles(current_user["schema_name"], db)


@router.post("", response_model=RoleResponse, status_code=201)
async def create_new_role(
    data: CreateRoleRequest,
    current_user: dict = Depends(require_permission("config.roles", "edit")),
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await create_role(
            data,
            current_user["schema_name"],
            current_user["user_id"],
            db
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{role_id}", response_model=RoleResponse)
async def get_single_role(
    role_id: UUID,
    current_user: dict = Depends(require_permission("config.roles", "view")),
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await get_role(role_id, current_user["schema_name"], db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_existing_role(
    role_id: UUID,
    data: UpdateRoleRequest,
    current_user: dict = Depends(require_permission("config.roles", "edit")),
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await update_role(role_id, data, current_user["schema_name"], db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{role_id}")
async def delete_existing_role(
    role_id: UUID,
    current_user: dict = Depends(require_permission("config.roles", "edit")),
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await delete_role(role_id, current_user["schema_name"], db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))