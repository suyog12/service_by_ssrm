from fastapi import APIRouter, Depends, Form
from app.core.dependencies import get_current_user, get_current_admin
from app.core.database import get_db
import asyncpg
from app.services import subscription_service
from app.core.r2 import get_r2_client
from app.core.config import settings
import uuid

router = APIRouter(prefix="/subscription", tags=["Subscription"])


@router.get("")
async def get_subscription(
    current_user: dict = Depends(get_current_admin),
    db: asyncpg.Connection = Depends(get_db)
):
    return await subscription_service.get_subscription(db, current_user["schema_name"])


@router.get("/plans")
async def get_plans(
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
):
    return await subscription_service.get_plans(db)


@router.get("/history")
async def get_history(
    current_user: dict = Depends(get_current_admin),
    db: asyncpg.Connection = Depends(get_db)
):
    return await subscription_service.get_history(db, current_user["schema_name"])


@router.get("/renew")
async def get_renew_info(
    current_user: dict = Depends(get_current_admin),
    db: asyncpg.Connection = Depends(get_db)
):
    return await subscription_service.get_renew_info(db, current_user["schema_name"])


@router.post("/payment-receipt/upload-url")
async def get_receipt_upload_url(
    filename: str,
    current_user: dict = Depends(get_current_admin),
    db: asyncpg.Connection = Depends(get_db)
):
    schema = current_user["schema_name"]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    key = f"payment-receipts/{schema}/{uuid.uuid4()}.{ext}"
    r2 = get_r2_client()
    url = r2.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": key,
            "ContentType": f"image/{ext}"
        },
        ExpiresIn=300
    )
    public_url = f"{settings.R2_PUBLIC_URL}/{key}"
    return {"upload_url": url, "key": key, "public_url": public_url}


@router.post("/payment-receipt", status_code=201)
async def submit_payment_receipt(
    plan_code: str = Form(...),
    amount_npr: float = Form(...),
    payment_reference: str = Form(...),
    receipt_key: str = Form(...),
    receipt_url: str = Form(...),
    current_user: dict = Depends(get_current_admin),
    db: asyncpg.Connection = Depends(get_db)
):
    schema = current_user["schema_name"]
    tenant_row = await db.fetchrow(
        "SELECT email FROM core.tenants WHERE schema_name = $1", schema
    )
    return await subscription_service.submit_payment_receipt(
        db=db,
        schema=schema,
        data={
            "plan_code": plan_code,
            "amount_npr": amount_npr,
            "payment_reference": payment_reference,
            "receipt_key": receipt_key,
            "receipt_url": receipt_url
        },
        tenant_admin_email=tenant_row["email"] if tenant_row else None
    )