from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID


# Feature 

class FeatureResponse(BaseModel):
    id: UUID
    code: str
    name: str
    module: str
    description: Optional[str] = None


# Role Template 

class PermissionInput(BaseModel):
    feature_code: str
    access_level: str               # 'none', 'view', 'edit'


class CreateRoleRequest(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[PermissionInput] = []


class UpdateRoleRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[PermissionInput]] = None


class RolePermissionResponse(BaseModel):
    feature_code: str
    feature_name: str
    module: str
    access_level: str


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    is_system: bool
    permissions: List[RolePermissionResponse] = []


class RoleListResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    is_system: bool
    permission_count: int