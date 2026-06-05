import re
import asyncpg

from app.utils.password import hash_password
from app.schemas.auth import TenantRegisterRequest, RegisterResponse
from app.utils.email import send_registration_confirmation_email


def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    slug = re.sub(r'^-+|-+$', '', slug)
    return slug


def schema_name_from_slug(slug: str) -> str:
    safe = slug.replace("-", "_")
    return f"tenant_{safe}"


async def register_tenant(
    data: TenantRegisterRequest, db: asyncpg.Connection
) -> RegisterResponse:
    if not data.business_name or not data.business_name.strip():
        raise ValueError("Business name cannot be empty")

    if len(data.business_name) > 255:
        raise ValueError("Business name is too long (maximum 255 characters)")

    if data.business_type not in ("restaurant", "hotel", "both"):
        raise ValueError("Business type must be restaurant, hotel, or both")

    slug = slugify(data.business_name)
    schema_name = schema_name_from_slug(slug)

    existing = await db.fetchrow(
        "SELECT id FROM core.tenants WHERE slug = $1",
        slug
    )
    if existing:
        raise ValueError(
            f"A business with the name '{data.business_name}' already exists"
        )

    tenant = await db.fetchrow(
        """
        INSERT INTO core.tenants (
            name, slug, type, email, phone, city, schema_name
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        data.business_name,
        slug,
        data.business_type,
        data.business_email,
        data.business_phone,
        data.city,
        schema_name
    )

    tenant_id = tenant["id"]

    password_hash = hash_password(data.admin_password)

    user = await db.fetchrow(
        """
        INSERT INTO core.users (
            tenant_id, full_name, email, phone, password_hash, is_admin
        )
        VALUES ($1, $2, $3, $4, $5, TRUE)
        RETURNING id
        """,
        tenant_id,
        data.admin_full_name,
        data.admin_email,
        data.admin_phone,
        password_hash
    )

    user_id = user["id"]

    await db.execute(
        "SELECT core.provision_tenant($1)",
        schema_name
    )

    await db.execute(
        f"""
        INSERT INTO "{schema_name}".user_profiles (id, is_admin, display_name)
        VALUES ($1, TRUE, $2)
        """,
        user_id,
        data.admin_full_name
    )

    await db.execute(
        f"""
        INSERT INTO "{schema_name}".notification_settings
            (event_code, in_app, sms_enabled, email_enabled)
        VALUES
            ('low_stock',           TRUE, TRUE,  TRUE),
            ('expiry_approaching',  TRUE, TRUE,  TRUE),
            ('discount_approval',   TRUE, TRUE,  TRUE),
            ('late_checkin',        TRUE, FALSE, FALSE),
            ('shift_handover',      TRUE, FALSE, FALSE),
            ('order_ready',         TRUE, FALSE, FALSE),
            ('new_order',           TRUE, FALSE, FALSE),
            ('bill_voided',         TRUE, FALSE, FALSE),
            ('room_checkout',       TRUE, FALSE, FALSE),
            ('housekeeping_task',   TRUE, FALSE, FALSE)
        """
    )

    await db.execute(
        f'INSERT INTO "{schema_name}".kitchen_settings DEFAULT VALUES'
    )

    await db.execute(
        f'INSERT INTO "{schema_name}".cash_settings DEFAULT VALUES'
    )

    await db.execute(
        f'INSERT INTO "{schema_name}".hr_settings DEFAULT VALUES'
    )

    # Create default outlet — represents the main business itself
    outlet_type = "hotel" if data.business_type == "hotel" else "restaurant"

    outlet = await db.fetchrow(
        f"""
        INSERT INTO "{schema_name}".outlets
            (name, type, is_default, kitchen_mode)
        VALUES ($1, $2, TRUE, 'single_printer')
        RETURNING id
        """,
        data.business_name,
        outlet_type,
    )

    outlet_id = outlet["id"]

    # Create default billing settings for the default outlet
    await db.execute(
        f"""
        INSERT INTO "{schema_name}".billing_settings (outlet_id)
        VALUES ($1)
        """,
        outlet_id
    )

    send_registration_confirmation_email(
        to_email=data.admin_email,
        full_name=data.admin_full_name,
        business_name=data.business_name,
        business_slug=slug
    )

    return RegisterResponse(
        message="Business registered successfully",
        tenant_id=tenant_id,
        admin_user_id=user_id,
        schema_name=schema_name
    )