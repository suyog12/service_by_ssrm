from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID


# Create Staff Account 

class CreateUserRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    role_template_id: Optional[UUID] = None


class CreateUserResponse(BaseModel):
    message: str
    user_id: UUID
    full_name: str
    email: str


# User Profile 

class UserProfileResponse(BaseModel):
    user_id: UUID
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    is_admin: bool
    designation: Optional[str]
    department: Optional[str]
    role_template_id: Optional[UUID]
    role_template_name: Optional[str]


# Assign Role 

class AssignRoleRequest(BaseModel):
    user_id: UUID
    role_template_id: UUID


class AssignRoleResponse(BaseModel):
    message: str


# Update User 

class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


# Permission Override 

class PermissionOverrideRequest(BaseModel):
    user_id: UUID
    feature_code: str
    access_level: str                   # 'none', 'view', 'edit'


class PermissionOverrideResponse(BaseModel):
    message: str