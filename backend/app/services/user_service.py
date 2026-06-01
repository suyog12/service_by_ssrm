from uuid import UUID
import asyncpg

from app.utils.password import hash_password
from app.utils.email import send_welcome_email
from app.services.auth_service import generate_temp_password
from app.schemas.user import (
    CreateUserRequest, CreateUserResponse,
    AssignRoleRequest, AssignRoleResponse,
    UpdateUserRequest,
    PermissionOverrideRequest, PermissionOverrideResponse,
    UserProfileResponse
)


async def create_user(
    data: CreateUserRequest,
    tenant_id: UUID,
    schema_name: str,
    business_name: str,
    created_by: UUID,
    db: asyncpg.Connection
) -> CreateUserResponse:
    # 1. Check email not already taken
    existing = await db.fetchrow(
        "SELECT id FROM core.users WHERE tenant_id = $1 AND email = $2",
        tenant_id, data.email
    )
    if existing:
        raise ValueError("A user with this email already exists")

    # 2. Generate temporary password
    temp_password = generate_temp_password()
    password_hash = hash_password(temp_password)

    # 3. Create in core.users — must_change_password = TRUE
    user = await db.fetchrow(
        """
        INSERT INTO core.users
            (tenant_id, full_name, email, phone, password_hash,
             is_admin, must_change_password)
        VALUES ($1, $2, $3, $4, $5, FALSE, TRUE)
        RETURNING id
        """,
        tenant_id, data.full_name, data.email, data.phone, password_hash
    )
    user_id = user["id"]

    # 4. Create profile in tenant schema
    await db.execute(
        f"""
        INSERT INTO "{schema_name}".user_profiles
            (id, display_name, role_template_id, created_by)
        VALUES ($1, $2, $3, $4)
        """,
        user_id, data.full_name, data.role_template_id, created_by
    )

    # 5. Send welcome email with temp password
    send_welcome_email(
        to_email=data.email,
        full_name=data.full_name,
        temp_password=temp_password,
        business_name=business_name
    )

    return CreateUserResponse(
        message="User created successfully. Login details sent to their email.",
        user_id=user_id,
        full_name=data.full_name,
        email=data.email
    )


async def assign_role(
    data: AssignRoleRequest,
    schema_name: str,
    db: asyncpg.Connection
) -> AssignRoleResponse:
    role = await db.fetchrow(
        f'SELECT id FROM "{schema_name}".role_templates WHERE id = $1',
        data.role_template_id
    )
    if not role:
        raise ValueError("Role template not found")

    await db.execute(
        f"""
        UPDATE "{schema_name}".user_profiles
        SET role_template_id = $1, updated_at = NOW()
        WHERE id = $2
        """,
        data.role_template_id, data.user_id
    )
    return AssignRoleResponse(message="Role assigned successfully")


async def update_user(
    user_id: UUID,
    data: UpdateUserRequest,
    schema_name: str,
    db: asyncpg.Connection
):
    if data.full_name is not None or data.is_active is not None:
        await db.execute(
            """
            UPDATE core.users
            SET full_name  = COALESCE($1, full_name),
                is_active  = COALESCE($2, is_active),
                updated_at = NOW()
            WHERE id = $3
            """,
            data.full_name, data.is_active, user_id
        )

    if data.designation is not None or data.department is not None:
        await db.execute(
            f"""
            UPDATE "{schema_name}".user_profiles
            SET designation = COALESCE($1, designation),
                department  = COALESCE($2, department),
                updated_at  = NOW()
            WHERE id = $3
            """,
            data.designation, data.department, user_id
        )

    return {"message": "User updated successfully"}


async def set_permission_override(
    data: PermissionOverrideRequest,
    schema_name: str,
    granted_by: UUID,
    db: asyncpg.Connection
) -> PermissionOverrideResponse:
    # Validate feature_code exists
    valid = await db.fetchrow(
        "SELECT id FROM core.features WHERE code = $1",
        data.feature_code
    )
    if not valid:
        raise ValueError(f"Feature code '{data.feature_code}' does not exist")

    await db.execute(
        f"""
        INSERT INTO "{schema_name}".user_permission_overrides
            (user_id, feature_code, access_level, granted_by)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, feature_code)
        DO UPDATE SET access_level = $3, granted_by = $4
        """,
        data.user_id, data.feature_code, data.access_level, granted_by
    )
    return PermissionOverrideResponse(message="Permission updated successfully")


async def get_user_permissions(
    user_id: UUID,
    schema_name: str,
    db: asyncpg.Connection
) -> dict:
    role_permissions = await db.fetch(
        f"""
        SELECT rp.feature_code, rp.access_level
        FROM "{schema_name}".role_permissions rp
        JOIN "{schema_name}".user_profiles up ON up.role_template_id = rp.role_template_id
        WHERE up.id = $1
        """,
        user_id
    )
    permissions = {row["feature_code"]: row["access_level"] for row in role_permissions}

    overrides = await db.fetch(
        f"""
        SELECT feature_code, access_level
        FROM "{schema_name}".user_permission_overrides
        WHERE user_id = $1
        """,
        user_id
    )
    for override in overrides:
        permissions[override["feature_code"]] = override["access_level"]

    return permissions


async def get_user_profile(
    user_id: UUID,
    schema_name: str,
    db: asyncpg.Connection
) -> UserProfileResponse:
    row = await db.fetchrow(
        f"""
        SELECT
            u.id, u.full_name, u.email, u.phone, u.is_admin,
            up.designation, up.department,
            up.role_template_id,
            rt.name as role_template_name
        FROM core.users u
        LEFT JOIN "{schema_name}".user_profiles up ON up.id = u.id
        LEFT JOIN "{schema_name}".role_templates rt ON rt.id = up.role_template_id
        WHERE u.id = $1
        """,
        user_id
    )
    if not row:
        raise ValueError("User not found")

    return UserProfileResponse(
        user_id=row["id"],
        full_name=row["full_name"],
        email=row["email"],
        phone=row["phone"],
        is_admin=row["is_admin"],
        designation=row["designation"],
        department=row["department"],
        role_template_id=row["role_template_id"],
        role_template_name=row["role_template_name"]
    )