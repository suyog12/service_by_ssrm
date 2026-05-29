from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID


# Register Business 

class TenantRegisterRequest(BaseModel):
    business_name: str
    business_type: str                  # 'restaurant', 'hotel', 'both'
    business_email: EmailStr
    business_phone: str
    city: str
    admin_full_name: str
    admin_email: EmailStr
    admin_password: str
    admin_phone: Optional[str] = None


class RegisterResponse(BaseModel):
    message: str
    tenant_id: UUID
    admin_user_id: UUID
    schema_name: str


# Login 

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_slug: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: UUID
    full_name: str
    is_admin: bool
    schema_name: str
    must_change_password: bool          # frontend forces password change if true


# Change Password (first login) 

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    message: str


# Refresh Token 

class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Token Payload (internal) 

class TokenPayload(BaseModel):
    user_id: UUID
    tenant_id: UUID
    schema_name: str
    is_admin: bool
    is_super_admin: bool
    type: str