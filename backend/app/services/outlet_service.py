from uuid import UUID
from fastapi import HTTPException
from app.schemas.outlet import OUTLET_LIMITS


async def _get_tenant_tier(db, schema: str) -> str:
    tenant = await db.fetchrow(
        'SELECT subscription_tier FROM core.tenants WHERE schema_name = $1',
        schema
    )
    return tenant["subscription_tier"] if tenant else "ez"


async def _check_outlet_limit(db, schema: str):
    tier = await _get_tenant_tier(db, schema)
    limit = OUTLET_LIMITS.get(tier)
    if limit is None:
        return  # unlimited

    count = await db.fetchval(
        f'SELECT COUNT(*) FROM "{schema}".outlets WHERE is_active = TRUE'
    )
    if count >= limit:
        raise HTTPException(
            400,
            f"Your {tier.upper()} plan allows a maximum of {limit} outlet(s). "
            f"Upgrade your plan to add more outlets."
        )


async def create_outlet(db, schema: str, data: dict) -> dict:
    await _check_outlet_limit(db, schema)

    # Check name uniqueness
    existing = await db.fetchrow(
        f'SELECT id FROM "{schema}".outlets WHERE name = $1',
        data["name"]
    )
    if existing:
        raise HTTPException(400, "An outlet with this name already exists")

    # Validate menu_source_id if provided
    if data.get("menu_source_id"):
        source = await db.fetchrow(
            f'SELECT id FROM "{schema}".outlets WHERE id = $1',
            data["menu_source_id"]
        )
        if not source:
            raise HTTPException(400, "Menu source outlet not found")

    # Validate inventory_source_id if provided
    if data.get("inventory_source_id"):
        source = await db.fetchrow(
            f'SELECT id FROM "{schema}".outlets WHERE id = $1',
            data["inventory_source_id"]
        )
        if not source:
            raise HTTPException(400, "Inventory source outlet not found")

    # Check if this is the first outlet — make it default
    count = await db.fetchval(
        f'SELECT COUNT(*) FROM "{schema}".outlets'
    )
    is_default = count == 0

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".outlets
            (name, type, address, phone, kitchen_mode,
             menu_source_id, inventory_source_id, is_default)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        data["name"],
        data.get("type", "restaurant"),
        data.get("address"),
        data.get("phone"),
        data.get("kitchen_mode", "single_printer"),
        data.get("menu_source_id"),
        data.get("inventory_source_id"),
        is_default,
    )

    outlet = dict(row)

    # If first outlet, auto-create billing settings for it
    if is_default:
        await db.execute(
            f"""
            INSERT INTO "{schema}".billing_settings (outlet_id)
            VALUES ($1)
            """,
            outlet["id"]
        )

    # If menu_source_id provided, copy menu from source outlet
    if data.get("menu_source_id"):
        await _copy_menu(db, schema, data["menu_source_id"], outlet["id"])

    # If inventory_source_id provided and not sharing, copy ingredients
    if data.get("inventory_source_id"):
        # source_outlet_id set means sharing — no copy needed
        # if they want a copy we do a full copy with source_outlet_id = NULL
        pass  # sharing handled via source_outlet_id on ingredients table

    return outlet


async def _copy_menu(
    db, schema: str, source_outlet_id: UUID, target_outlet_id: UUID
):
    # Copy categories
    categories = await db.fetch(
        f"""
        SELECT * FROM "{schema}".menu_categories
        WHERE outlet_id = $1
        """,
        source_outlet_id
    )

    for cat in categories:
        new_cat = await db.fetchrow(
            f"""
            INSERT INTO "{schema}".menu_categories
                (outlet_id, name, description, image_url, sort_order, is_active)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (outlet_id, name) DO NOTHING
            RETURNING id
            """,
            target_outlet_id,
            cat["name"],
            cat["description"],
            cat["image_url"],
            cat["sort_order"],
            cat["is_active"],
        )
        if not new_cat:
            continue

        # Copy items in this category
        items = await db.fetch(
            f"""
            SELECT * FROM "{schema}".menu_items
            WHERE outlet_id = $1 AND category_id = $2
            """,
            source_outlet_id, cat["id"]
        )

        for item in items:
            await db.execute(
                f"""
                INSERT INTO "{schema}".menu_items
                    (outlet_id, category_id, name, description, image_url,
                     price, item_type, tax_rate, station,
                     allows_special_inst, is_available, sort_order)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (outlet_id, name) DO NOTHING
                """,
                target_outlet_id,
                new_cat["id"],
                item["name"],
                item["description"],
                item["image_url"],
                item["price"],
                item["item_type"],
                item["tax_rate"],
                item["station"],
                item["allows_special_inst"],
                item["is_available"],
                item["sort_order"],
            )


async def list_outlets(db, schema: str, active_only: bool = False) -> list[dict]:
    if active_only:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".outlets
            WHERE is_active = TRUE
            ORDER BY sort_order, created_at
            """
        )
    else:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".outlets
            ORDER BY sort_order, created_at
            """
        )
    return [dict(r) for r in rows]


async def get_outlet(db, schema: str, outlet_id: UUID) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".outlets WHERE id = $1',
        outlet_id
    )
    if not row:
        raise HTTPException(404, "Outlet not found")
    return dict(row)


async def update_outlet(
    db, schema: str, outlet_id: UUID, data: dict
) -> dict:
    await get_outlet(db, schema, outlet_id)

    if "name" in data and data["name"]:
        existing = await db.fetchrow(
            f"""
            SELECT id FROM "{schema}".outlets
            WHERE name = $1 AND id != $2
            """,
            data["name"], outlet_id
        )
        if existing:
            raise HTTPException(400, "An outlet with this name already exists")

    fields = []
    values = []
    idx = 1
    for field in ["name", "type", "address", "phone",
                  "kitchen_mode", "is_active", "sort_order"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1

    if not fields:
        return await get_outlet(db, schema, outlet_id)

    values.append(outlet_id)
    await db.execute(
        f"""
        UPDATE "{schema}".outlets
        SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        """,
        *values
    )
    return await get_outlet(db, schema, outlet_id)


async def get_default_outlet_id(db, schema: str) -> UUID:
    row = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".outlets
        WHERE is_default = TRUE
        LIMIT 1
        """
    )
    if not row:
        # Fall back to first outlet
        row = await db.fetchrow(
            f"""
            SELECT id FROM "{schema}".outlets
            ORDER BY created_at
            LIMIT 1
            """
        )
    if not row:
        raise HTTPException(400, "No outlets configured for this tenant")
    return row["id"]