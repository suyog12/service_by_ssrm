from uuid import UUID
from typing import List
import asyncpg

from app.schemas.role import (
    CreateRoleRequest, UpdateRoleRequest,
    RoleResponse, RoleListResponse,
    RolePermissionResponse, FeatureResponse
)


async def get_all_features(db: asyncpg.Connection) -> List[FeatureResponse]:
    rows = await db.fetch(
        "SELECT id, code, name, module, description FROM core.features ORDER BY module, name"
    )
    return [FeatureResponse(**dict(row)) for row in rows]


async def create_role(
    data: CreateRoleRequest,
    schema_name: str,
    created_by: UUID,
    db: asyncpg.Connection
) -> RoleResponse:
    # 1. Check name not taken
    existing = await db.fetchrow(
        f'SELECT id FROM "{schema_name}".role_templates WHERE name = $1',
        data.name
    )
    if existing:
        raise ValueError(f"Role '{data.name}' already exists")

    # 2. Create role template
    role = await db.fetchrow(
        f"""
        INSERT INTO "{schema_name}".role_templates (name, description, created_by)
        VALUES ($1, $2, $3)
        RETURNING id, name, description, is_system
        """,
        data.name, data.description, created_by
    )
    role_id = role["id"]
    
    # Validate all permission access levels before inserting
    valid_levels = {"none", "view", "edit"}
    for perm in data.permissions:
        if perm.access_level not in valid_levels:
            raise ValueError(
                f"Invalid access_level '{perm.access_level}'. Must be none, view, or edit."
            )

    # 3. Insert permissions
    if data.permissions:
        await db.executemany(
            f"""
            INSERT INTO "{schema_name}".role_permissions
                (role_template_id, feature_code, access_level)
            VALUES ($1, $2, $3)
            ON CONFLICT (role_template_id, feature_code)
            DO UPDATE SET access_level = $3
            """,
            [(role_id, p.feature_code, p.access_level) for p in data.permissions]
        )

    return await get_role(role_id, schema_name, db)


async def get_role(
    role_id: UUID,
    schema_name: str,
    db: asyncpg.Connection
) -> RoleResponse:
    role = await db.fetchrow(
        f"""
        SELECT id, name, description, is_system
        FROM "{schema_name}".role_templates
        WHERE id = $1
        """,
        role_id
    )
    if not role:
        raise ValueError("Role not found")

    permissions = await db.fetch(
        f"""
        SELECT rp.feature_code, rp.access_level,
               f.name as feature_name, f.module
        FROM "{schema_name}".role_permissions rp
        JOIN core.features f ON f.code = rp.feature_code
        WHERE rp.role_template_id = $1
        ORDER BY f.module, f.name
        """,
        role_id
    )

    return RoleResponse(
        id=role["id"],
        name=role["name"],
        description=role["description"],
        is_system=role["is_system"],
        permissions=[
            RolePermissionResponse(
                feature_code=p["feature_code"],
                feature_name=p["feature_name"],
                module=p["module"],
                access_level=p["access_level"]
            ) for p in permissions
        ]
    )


async def list_roles(
    schema_name: str,
    db: asyncpg.Connection
) -> List[RoleListResponse]:
    rows = await db.fetch(
        f"""
        SELECT
            rt.id, rt.name, rt.description, rt.is_system,
            COUNT(rp.id) as permission_count
        FROM "{schema_name}".role_templates rt
        LEFT JOIN "{schema_name}".role_permissions rp ON rp.role_template_id = rt.id
        GROUP BY rt.id, rt.name, rt.description, rt.is_system
        ORDER BY rt.name
        """
    )
    return [RoleListResponse(**dict(row)) for row in rows]


async def update_role(
    role_id: UUID,
    data: UpdateRoleRequest,
    schema_name: str,
    db: asyncpg.Connection
) -> RoleResponse:
    # Check role exists and is not system
    role = await db.fetchrow(
        f'SELECT id, is_system FROM "{schema_name}".role_templates WHERE id = $1',
        role_id
    )
    if not role:
        raise ValueError("Role not found")
    if role["is_system"]:
        raise ValueError("System roles cannot be modified")

    # Update name/description
    if data.name or data.description:
        await db.execute(
            f"""
            UPDATE "{schema_name}".role_templates
            SET name        = COALESCE($1, name),
                description = COALESCE($2, description),
                updated_at  = NOW()
            WHERE id = $3
            """,
            data.name, data.description, role_id
        )

    # Replace permissions if provided
    if data.permissions is not None:
        await db.execute(
            f'DELETE FROM "{schema_name}".role_permissions WHERE role_template_id = $1',
            role_id
        )
        if data.permissions:
            await db.executemany(
                f"""
                INSERT INTO "{schema_name}".role_permissions
                    (role_template_id, feature_code, access_level)
                VALUES ($1, $2, $3)
                """,
                [(role_id, p.feature_code, p.access_level) for p in data.permissions]
            )

    return await get_role(role_id, schema_name, db)


async def delete_role(
    role_id: UUID,
    schema_name: str,
    db: asyncpg.Connection
) -> dict:
    role = await db.fetchrow(
        f'SELECT id, is_system FROM "{schema_name}".role_templates WHERE id = $1',
        role_id
    )
    if not role:
        raise ValueError("Role not found")
    if role["is_system"]:
        raise ValueError("System roles cannot be deleted")

    # Check if any users are assigned this role
    users = await db.fetchrow(
        f"""
        SELECT COUNT(*) as count FROM "{schema_name}".user_profiles
        WHERE role_template_id = $1
        """,
        role_id
    )
    if users["count"] > 0:
        raise ValueError(
            f"Cannot delete role — {users['count']} user(s) are assigned to it. Reassign them first."
        )

    await db.execute(
        f'DELETE FROM "{schema_name}".role_templates WHERE id = $1',
        role_id
    )
    return {"message": "Role deleted successfully"}