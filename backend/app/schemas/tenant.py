from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    type: str
    email: Optional[str]
    phone: Optional[str]
    city: Optional[str]
    schema_name: str
    onboarding_complete: bool
    subscription_tier: str
    vat_registered: bool
    service_charge_pct: float
    vat_pct: float