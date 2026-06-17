from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from uuid import UUID
import asyncpg

from app.core.security import decode_token
from app.core.database import get_db

bearer_scheme = HTTPBearer()


# Subscription tier feature gates
# Features not available on certain tiers
TIER_RESTRICTIONS = {
    "ez": {
        "hotel.checkin", "hotel.rooms", "hotel.housekeeping",
        "hotel.room_charges", "hotel.reservations", "hotel.guests",
        "analytics.full", "analytics.financial", "analytics.export",
        "comms.announcements",
    },
    "pro": set(),   # pro has access to everything except enterprise features
    "max": set(),
    "enterprise": set(),
}

ACCESS_LEVELS = {"none": 0, "view": 1, "edit": 2}


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

    row = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".outlets
        WHERE is_default = TRUE AND is_active = TRUE
        LIMIT 1
        """
    )
    if not row:
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


async def _build_user_context(payload: dict, db: asyncpg.Connection, request: Request) -> dict:
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


async def _decode_and_validate(
    credentials: HTTPAuthorizationCredentials,
    db: asyncpg.Connection,
    check_must_change: bool = False
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

    if check_must_change and user["must_change_password"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must change your password before continuing"
        )

    return payload


async def _get_user_permissions(user_id: UUID, schema: str, db: asyncpg.Connection) -> dict:
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

    return permissions


async def _check_tier(feature_code: str, schema: str, db: asyncpg.Connection):
    tenant = await db.fetchrow(
        "SELECT subscription_tier FROM core.tenants WHERE schema_name = $1",
        schema
    )
    if not tenant:
        return
    tier = tenant["subscription_tier"]
    restricted = TIER_RESTRICTIONS.get(tier, set())
    if feature_code in restricted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This feature is not available on the {tier} plan. Please upgrade."
        )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: asyncpg.Connection = Depends(get_db)
) -> dict:
    payload = await _decode_and_validate(credentials, db)
    return await _build_user_context(payload, db, request)


async def get_current_user_strict(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: asyncpg.Connection = Depends(get_db)
) -> dict:
    payload = await _decode_and_validate(credentials, db, check_must_change=True)
    return await _build_user_context(payload, db, request)


async def get_current_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    if not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_feature(feature_code: str, level: str = "view"):
    """
    Dependency that enforces JWT auth + subscription tier + role-based feature access.

    Flow:
      1. Decode JWT — get user_id, schema_name, is_admin
      2. Check subscription tier allows the feature
      3. Admin bypasses role check — allow immediately
      4. Non-admin: check role_permissions + user_permission_overrides
      5. 403 if insufficient access level
    """
    async def checker(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        db: asyncpg.Connection = Depends(get_db)
    ) -> dict:
        payload = await _decode_and_validate(credentials, db, check_must_change=True)
        schema = payload["schema_name"]

        # Tier check — applies to everyone including admins
        await _check_tier(feature_code, schema, db)

        ctx = await _build_user_context(payload, db, request)

        # Admin bypass
        if payload["is_admin"]:
            return ctx

        # Role + override check
        permissions = await _get_user_permissions(ctx["user_id"], schema, db)
        user_level = ACCESS_LEVELS.get(permissions.get(feature_code, "none"), 0)
        required_level = ACCESS_LEVELS.get(level, 1)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have {level} access to {feature_code}"
            )

        return ctx

    return checker


# Legacy aliases — kept so existing endpoint files don't break during migration
require_admin = get_current_admin
require_permission = require_feature