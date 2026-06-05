from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from uuid import UUID
import asyncpg

from app.core.security import decode_token
from app.core.database import get_db

bearer_scheme = HTTPBearer()


async def _resolve_outlet_id(db, schema: str, outlet_header: str = None) -> UUID:
    if outlet_header:
        try:
            outlet_id = UUID(outlet_header)
            row = await db.fetchrow(
                f'SELECT id FROM "{schema}".outlets WHERE id = $1 AND is_active = TRUE',
                outlet_id
            )
            if row:
                return row["id"]
        except (ValueError, Exception):
            pass

    # Fall back to default outlet
    row = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".outlets
        WHERE is_default = TRUE AND is_active = TRUE
        LIMIT 1
        """
    )
    if not row:
        # Fall back to first outlet
        row = await db.fetchrow(
            f"""
            SELECT id FROM "{schema}".outlets
            ORDER BY created_at
            LIMIT 1
            """
        )
    if not row:
        return None
    return row["id"]


async def get_current_user(
    request: Request,
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

    schema = payload["schema_name"]
    outlet_header = request.headers.get("X-Outlet-ID")
    outlet_id = await _resolve_outlet_id(db, schema, outlet_header)

    return {
        "user_id": UUID(payload["user_id"]),
        "tenant_id": UUID(payload["tenant_id"]),
        "schema_name": schema,
        "outlet_id": outlet_id,
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
    async def checker(
        request: Request,
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

        schema = payload["schema_name"]
        outlet_header = request.headers.get("X-Outlet-ID")
        outlet_id = await _resolve_outlet_id(db, schema, outlet_header)

        if payload["is_admin"]:
            return {
                "user_id": UUID(payload["user_id"]),
                "tenant_id": UUID(payload["tenant_id"]),
                "schema_name": schema,
                "outlet_id": outlet_id,
                "is_admin": payload["is_admin"],
                "is_super_admin": payload["is_super_admin"],
            }

        user_id = UUID(payload["user_id"])

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

        access_levels = {"none": 0, "view": 1, "edit": 2}
        user_level = access_levels.get(permissions.get(feature_code, "none"), 0)
        required_level = access_levels.get(level, 1)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have {level} access to {feature_code}"
            )

        return {
            "user_id": UUID(payload["user_id"]),
            "tenant_id": UUID(payload["tenant_id"]),
            "schema_name": schema,
            "outlet_id": outlet_id,
            "is_admin": payload["is_admin"],
            "is_super_admin": payload["is_super_admin"],
        }

    return checker


async def get_current_user_strict(
    request: Request,
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
        "SELECT id, is_active, must_change_password FROM core.users WHERE id = $1",
        UUID(payload["user_id"])
    )

    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated"
        )

    if user["must_change_password"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must change your password before continuing"
        )

    schema = payload["schema_name"]
    outlet_header = request.headers.get("X-Outlet-ID")
    outlet_id = await _resolve_outlet_id(db, schema, outlet_header)

    return {
        "user_id": UUID(payload["user_id"]),
        "tenant_id": UUID(payload["tenant_id"]),
        "schema_name": schema,
        "outlet_id": outlet_id,
        "is_admin": payload["is_admin"],
        "is_super_admin": payload["is_super_admin"],
    }


# Alias used across endpoint files for admin-only routes
require_admin = get_current_admin