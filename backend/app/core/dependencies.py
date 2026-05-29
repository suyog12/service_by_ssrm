from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from uuid import UUID
import asyncpg

from app.core.security import decode_token
from app.core.database import get_db

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: asyncpg.Connection = Depends(get_db)
) -> dict:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user = await db.fetchrow(
        "SELECT id, is_active FROM core.users WHERE id = $1",
        UUID(payload["user_id"])
    )

    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated"
        )

    return {
        "user_id": UUID(payload["user_id"]),
        "tenant_id": UUID(payload["tenant_id"]),
        "schema_name": payload["schema_name"],
        "is_admin": payload["is_admin"],
        "is_super_admin": payload["is_super_admin"],
    }


async def get_current_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    if not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_permission(feature_code: str, level: str = "view"):
    """
    Usage in endpoint:
    Depends(require_permission("billing.void", "edit"))
    """
    async def checker(
        current_user: dict = Depends(get_current_user),
        db: asyncpg.Connection = Depends(get_db)
    ) -> dict:
        # Admins bypass all permission checks
        if current_user["is_admin"]:
            return current_user

        schema = current_user["schema_name"]
        user_id = current_user["user_id"]

        # Get role permissions
        role_perms = await db.fetch(
            f"""
            SELECT rp.feature_code, rp.access_level
            FROM "{schema}".role_permissions rp
            JOIN "{schema}".user_profiles up ON up.role_template_id = rp.role_template_id
            WHERE up.id = $1
            """,
            user_id
        )
        permissions = {r["feature_code"]: r["access_level"] for r in role_perms}

        # Apply overrides
        overrides = await db.fetch(
            f"""
            SELECT feature_code, access_level
            FROM "{schema}".user_permission_overrides
            WHERE user_id = $1
            """,
            user_id
        )
        for o in overrides:
            permissions[o["feature_code"]] = o["access_level"]

        # Check permission
        access_levels = {"none": 0, "view": 1, "edit": 2}
        user_level = access_levels.get(permissions.get(feature_code, "none"), 0)
        required_level = access_levels.get(level, 1)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have {level} access to {feature_code}"
            )

        return current_user

    return checker