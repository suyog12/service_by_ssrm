from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
import asyncpg
from typing import List

from app.core.database import get_db
from app.core.dependencies import (
    get_current_user,
    get_current_user_strict,
    get_current_admin,
    require_feature,
)
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
    current_user: dict = Depends(require_feature("hr.create_staff", "edit")),
    db: asyncpg.Connection = Depends(get_db)
):
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
    current_user: dict = Depends(get_current_user_strict),
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


@router.get("", response_model=List[UserProfileResponse])
async def list_staff(
    current_user: dict = Depends(require_feature("hr.view_staff", "view")),
    db: asyncpg.Connection = Depends(get_db)
):
    rows = await db.fetch(
        f"""
        SELECT
            u.id, u.full_name, u.email, u.phone, u.is_admin,
            up.designation, up.department,
            up.role_template_id,
            rt.name as role_template_name
        FROM core.users u
        LEFT JOIN "{current_user['schema_name']}".user_profiles up ON up.id = u.id
        LEFT JOIN "{current_user['schema_name']}".role_templates rt ON rt.id = up.role_template_id
        WHERE u.tenant_id = $1
        ORDER BY u.full_name
        """,
        current_user["tenant_id"]
    )
    return [
        UserProfileResponse(
            user_id=row["id"],
            full_name=row["full_name"],
            email=row["email"],
            phone=row["phone"],
            is_admin=row["is_admin"],
            designation=row["designation"],
            department=row["department"],
            role_template_id=row["role_template_id"],
            role_template_name=row["role_template_name"]
        ) for row in rows
    ]


@router.get("/{user_id}/permissions")
async def user_permissions(
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
):
    return await get_user_permissions(user_id, current_user["schema_name"], db)


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_profile(
    user_id: UUID,
    current_user: dict = Depends(require_feature("hr.view_staff", "view")),
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
    current_user: dict = Depends(require_feature("hr.create_staff", "edit")),
    db: asyncpg.Connection = Depends(get_db)
):
    return await update_user(user_id, data, current_user["schema_name"], db)


@router.patch("/{user_id}/deactivate")
async def deactivate_user(
    user_id: UUID,
    current_user: dict = Depends(get_current_admin),
    db: asyncpg.Connection = Depends(get_db)
):
    if user_id == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot deactivate yourself")
    await db.execute(
        "UPDATE core.users SET is_active = FALSE, updated_at = NOW() WHERE id = $1",
        user_id
    )
    return {"message": "User deactivated successfully"}


@router.patch("/{user_id}/reactivate")
async def reactivate_user(
    user_id: UUID,
    current_user: dict = Depends(get_current_admin),
    db: asyncpg.Connection = Depends(get_db)
):
    await db.execute(
        "UPDATE core.users SET is_active = TRUE, updated_at = NOW() WHERE id = $1",
        user_id
    )
    return {"message": "User reactivated successfully"}


@router.post("/assign-role", response_model=AssignRoleResponse)
async def assign(
    data: AssignRoleRequest,
    current_user: dict = Depends(require_feature("config.roles", "edit")),
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await assign_role(data, current_user["schema_name"], db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/permissions", response_model=PermissionOverrideResponse)
async def override_permission(
    data: PermissionOverrideRequest,
    current_user: dict = Depends(require_feature("config.roles", "edit")),
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await set_permission_override(
            data,
            current_user["schema_name"],
            current_user["user_id"],
            db
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))