from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
import asyncpg

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin, require_permission
from app.schemas.user import (
    CreateUserRequest, CreateUserResponse,
    AssignRoleRequest, AssignRoleResponse,
    UpdateUserRequest,
    PermissionOverrideRequest, PermissionOverrideResponse,
    UserProfileResponse
)
from app.services.user_service import (
    create_user,
    assign_role,
    update_user,
    set_permission_override,
    get_user_permissions,
    get_user_profile
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=CreateUserResponse, status_code=201)
async def create_staff(
    data: CreateUserRequest,
    current_user: dict = Depends(require_permission("hr.create_staff", "edit")),
    db: asyncpg.Connection = Depends(get_db)
):
    # Get business name for welcome email
    tenant = await db.fetchrow(
        "SELECT name FROM core.tenants WHERE id = $1",
        current_user["tenant_id"]
    )
    try:
        return await create_user(
            data=data,
            tenant_id=current_user["tenant_id"],
            schema_name=current_user["schema_name"],
            business_name=tenant["name"],
            created_by=current_user["user_id"],
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await get_user_profile(
            current_user["user_id"],
            current_user["schema_name"],
            db
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_profile(
    user_id: UUID,
    current_user: dict = Depends(require_permission("hr.view_staff", "view")),
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await get_user_profile(user_id, current_user["schema_name"], db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{user_id}")
async def update(
    user_id: UUID,
    data: UpdateUserRequest,
    current_user: dict = Depends(require_permission("hr.view_staff", "edit")),
    db: asyncpg.Connection = Depends(get_db)
):
    return await update_user(user_id, data, current_user["schema_name"], db)


@router.post("/assign-role", response_model=AssignRoleResponse)
async def assign(
    data: AssignRoleRequest,
    current_user: dict = Depends(require_permission("config.roles", "edit")),
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await assign_role(data, current_user["schema_name"], db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/permissions", response_model=PermissionOverrideResponse)
async def override_permission(
    data: PermissionOverrideRequest,
    current_user: dict = Depends(require_permission("config.roles", "edit")),
    db: asyncpg.Connection = Depends(get_db)
):
    return await set_permission_override(
        data,
        current_user["schema_name"],
        current_user["user_id"],
        db
    )


@router.get("/{user_id}/permissions")
async def user_permissions(
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
):
    return await get_user_permissions(user_id, current_user["schema_name"], db)