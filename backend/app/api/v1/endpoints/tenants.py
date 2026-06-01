from fastapi import APIRouter, Depends, HTTPException
import asyncpg

from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.schemas.tenant import TenantResponse

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get("/me", response_model=TenantResponse)
async def get_my_tenant(
    current_user: dict = Depends(get_current_admin),
    db: asyncpg.Connection = Depends(get_db)
):
    row = await db.fetchrow(
        """
        SELECT id, name, slug, type, email, phone, city,
               schema_name, onboarding_complete, subscription_tier,
               vat_registered, service_charge_pct, vat_pct
        FROM core.tenants WHERE id = $1
        """,
        current_user["tenant_id"]
    )
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantResponse(**dict(row))


@router.post("/me/complete-onboarding")
async def complete_onboarding(
    current_user: dict = Depends(get_current_admin),
    db: asyncpg.Connection = Depends(get_db)
):
    await db.execute(
        "UPDATE core.tenants SET onboarding_complete = TRUE, updated_at = NOW() WHERE id = $1",
        current_user["tenant_id"]
    )
    return {"message": "Onboarding marked as complete"}


@router.patch("/me")
async def update_tenant(
    current_user: dict = Depends(get_current_admin),
    db: asyncpg.Connection = Depends(get_db)
):
    pass  # We will expand this later