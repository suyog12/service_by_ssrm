import secrets
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID
import asyncpg

from app.utils.email import send_password_reset_email
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.utils.password import hash_password, verify_password
from app.schemas.auth import (
    LoginRequest, LoginResponse,
    RefreshResponse,
    ChangePasswordRequest, ChangePasswordResponse
)

def generate_temp_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def login_user(data: LoginRequest, db: asyncpg.Connection) -> LoginResponse:
    # 1. Find tenant by slug
    tenant = await db.fetchrow(
        "SELECT id, schema_name, is_active FROM core.tenants WHERE slug = $1",
        data.tenant_slug
    )
    if not tenant:
        raise ValueError("Business not found")
    if not tenant["is_active"]:
        raise ValueError("This account has been deactivated")

    # 2. Find user
    user = await db.fetchrow(
        """
        SELECT id, full_name, password_hash, is_active, is_admin,
               is_super_admin, must_change_password
        FROM core.users
        WHERE tenant_id = $1 AND email = $2
        """,
        tenant["id"], data.email
    )
    if not user:
        raise ValueError("Invalid email or password")
    if not user["is_active"]:
        raise ValueError("Your account has been deactivated")

    # 3. Verify password
    if not verify_password(data.password, user["password_hash"]):
        raise ValueError("Invalid email or password")

    # 4. Build token payload
    token_data = {
        "user_id": str(user["id"]),
        "tenant_id": str(tenant["id"]),
        "schema_name": tenant["schema_name"],
        "is_admin": user["is_admin"],
        "is_super_admin": user["is_super_admin"],
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # 5. Store refresh token
    token_hash = hash_password(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.execute(
        """
        INSERT INTO core.refresh_tokens (user_id, token_hash, expires_at)
        VALUES ($1, $2, $3)
        """,
        user["id"], token_hash, expires_at
    )

    # 6. Update last login
    await db.execute(
        "UPDATE core.users SET last_login_at = NOW() WHERE id = $1",
        user["id"]
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user["id"],
        full_name=user["full_name"],
        is_admin=user["is_admin"],
        schema_name=tenant["schema_name"],
        must_change_password=user["must_change_password"]
    )


async def change_password(
    user_id: UUID,
    data: ChangePasswordRequest,
    db: asyncpg.Connection
) -> ChangePasswordResponse:
    # 1. Get current password hash
    user = await db.fetchrow(
        "SELECT password_hash FROM core.users WHERE id = $1",
        user_id
    )
    if not user:
        raise ValueError("User not found")

    # 2. Verify current password
    if not verify_password(data.current_password, user["password_hash"]):
        raise ValueError("Current password is incorrect")

    # 3. Hash and save new password, clear must_change_password flag
    new_hash = hash_password(data.new_password)
    await db.execute(
        """
        UPDATE core.users
        SET password_hash = $1,
            must_change_password = FALSE,
            updated_at = NOW()
        WHERE id = $2
        """,
        new_hash, user_id
    )

    return ChangePasswordResponse(message="Password changed successfully")


async def refresh_access_token(refresh_token: str, db: asyncpg.Connection) -> RefreshResponse:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise ValueError("Invalid refresh token")

    user_id = UUID(payload.get("user_id"))

    stored_tokens = await db.fetch(
        """
        SELECT id, token_hash FROM core.refresh_tokens
        WHERE user_id = $1 AND revoked = FALSE AND expires_at > NOW()
        """,
        user_id
    )

    matched_token = None
    for stored in stored_tokens:
        if verify_password(refresh_token, stored["token_hash"]):
            matched_token = stored
            break

    if not matched_token:
        raise ValueError("Refresh token not found or expired")

    token_data = {
        "user_id": payload["user_id"],
        "tenant_id": payload["tenant_id"],
        "schema_name": payload["schema_name"],
        "is_admin": payload["is_admin"],
        "is_super_admin": payload["is_super_admin"],
    }

    return RefreshResponse(access_token=create_access_token(token_data))


async def logout_user(refresh_token: str, db: asyncpg.Connection) -> dict:
    payload = decode_token(refresh_token)
    if not payload:
        raise ValueError("Invalid token")

    user_id = UUID(payload.get("user_id"))
    stored_tokens = await db.fetch(
        "SELECT id, token_hash FROM core.refresh_tokens WHERE user_id = $1 AND revoked = FALSE",
        user_id
    )

    for stored in stored_tokens:
        if verify_password(refresh_token, stored["token_hash"]):
            await db.execute(
                "UPDATE core.refresh_tokens SET revoked = TRUE WHERE id = $1",
                stored["id"]
            )
            break

    return {"message": "Logged out successfully"}

async def forgot_password(
    email: str,
    tenant_slug: str,
    db: asyncpg.Connection
) -> dict:
    # 1. Find tenant
    tenant = await db.fetchrow(
        "SELECT id, name FROM core.tenants WHERE slug = $1",
        tenant_slug
    )
    if not tenant:
        # Return success anyway to prevent email enumeration
        return {"message": "If that email exists you will receive a reset link shortly"}

    # 2. Find user
    user = await db.fetchrow(
        "SELECT id, full_name, email FROM core.users WHERE tenant_id = $1 AND email = $2",
        tenant["id"], email
    )
    if not user:
        return {"message": "If that email exists you will receive a reset link shortly"}

    # 3. Invalidate any existing unused tokens for this user
    await db.execute(
        "UPDATE core.reset_tokens SET used = TRUE WHERE user_id = $1 AND used = FALSE",
        user["id"]
    )

    # 4. Generate reset token
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_password(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    await db.execute(
        """
        INSERT INTO core.reset_tokens (user_id, token_hash, expires_at)
        VALUES ($1, $2, $3)
        """,
        user["id"], token_hash, expires_at
    )

    # 5. Send email — fire and forget, never expose failure to caller
    send_password_reset_email(
        to_email=user["email"],
        full_name=user["full_name"],
        reset_token=raw_token,
        business_name=tenant["name"]
    )

    return {"message": "If that email exists you will receive a reset link shortly"}


async def reset_password(
    token: str,
    new_password: str,
    db: asyncpg.Connection
) -> dict:
    # 1. Find all valid unused tokens
    stored_tokens = await db.fetch(
        """
        SELECT id, user_id, token_hash
        FROM core.reset_tokens
        WHERE used = FALSE AND expires_at > NOW()
        """
    )

    matched = None
    for stored in stored_tokens:
        if verify_password(token, stored["token_hash"]):
            matched = stored
            break

    if not matched:
        raise ValueError("Reset token is invalid or has expired")

    # 2. Mark token as used
    await db.execute(
        "UPDATE core.reset_tokens SET used = TRUE WHERE id = $1",
        matched["id"]
    )

    # 3. Update password
    new_hash = hash_password(new_password)
    await db.execute(
        """
        UPDATE core.users
        SET password_hash = $1,
            must_change_password = FALSE,
            updated_at = NOW()
        WHERE id = $2
        """,
        new_hash, matched["user_id"]
    )

    return {"message": "Password reset successfully"}