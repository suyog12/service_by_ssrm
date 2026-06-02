from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.auth import (
    TenantRegisterRequest, RegisterResponse,
    LoginRequest, LoginResponse,
    RefreshRequest, RefreshResponse,
    ChangePasswordRequest, ChangePasswordResponse,
    ForgotPasswordRequest, ForgotPasswordResponse,
    ResetPasswordRequest, ResetPasswordResponse,
)
from app.services.auth_service import (
    login_user,
    refresh_access_token,
    logout_user,
    change_password,
    forgot_password,
    reset_password,
)
from app.services.tenant_service import register_tenant

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    data: TenantRegisterRequest,
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await register_tenant(data, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await login_user(data, db)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    data: RefreshRequest,
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await refresh_access_token(data.refresh_token, db)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout")
async def logout(
    data: RefreshRequest,
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await logout_user(data.refresh_token, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_pwd(
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await change_password(current_user["user_id"], data, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_pwd(
    data: ForgotPasswordRequest,
    db: asyncpg.Connection = Depends(get_db)
):
    return await forgot_password(data.email, data.tenant_slug, db)


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_pwd(
    data: ResetPasswordRequest,
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        return await reset_password(data.token, data.new_password, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user