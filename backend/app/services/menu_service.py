from uuid import UUID
from fastapi import HTTPException


async def create_category(
    db, schema: str, outlet_id: UUID, data: dict
) -> dict:
    existing = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".menu_categories
        WHERE name = $1 AND outlet_id = $2
        """,
        data["name"], outlet_id
    )
    if existing:
        raise HTTPException(
            400, f"A category named '{data['name']}' already exists"
        )

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".menu_categories
            (outlet_id, name, description, sort_order)
        VALUES ($1, $2, $3, $4)
        RETURNING id, name, description, sort_order, is_active
        """,
        outlet_id,
        data["name"],
        data.get("description"),
        data.get("sort_order", 0),
    )
    return dict(row)


async def list_categories(
    db, schema: str, outlet_id: UUID
) -> list[dict]:
    rows = await db.fetch(
        f"""
        SELECT id, name, description, sort_order, is_active
        FROM "{schema}".menu_categories
        WHERE outlet_id = $1
        ORDER BY sort_order, name
        """,
        outlet_id
    )
    return [dict(r) for r in rows]


async def update_category(
    db, schema: str, outlet_id: UUID,
    category_id: UUID, data: dict
) -> dict:
    category = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".menu_categories
        WHERE id = $1 AND outlet_id = $2
        """,
        category_id, outlet_id
    )
    if not category:
        raise HTTPException(404, "Category not found")

    if data.get("name"):
        existing = await db.fetchrow(
            f"""
            SELECT id FROM "{schema}".menu_categories
            WHERE name = $1 AND outlet_id = $2 AND id != $3
            """,
            data["name"], outlet_id, category_id
        )
        if existing:
            raise HTTPException(
                400, f"A category named '{data['name']}' already exists"
            )

    fields = []
    values = []
    idx = 1
    for field in ["name", "description", "sort_order", "is_active"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1

    if not fields:
        row = await db.fetchrow(
            f"""
            SELECT id, name, description, sort_order, is_active
            FROM "{schema}".menu_categories
            WHERE id = $1
            """,
            category_id
        )
        return dict(row)

    values.append(category_id)
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".menu_categories
        SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        RETURNING id, name, description, sort_order, is_active
        """,
        *values
    )
    return dict(row)


async def delete_category(
    db, schema: str, outlet_id: UUID, category_id: UUID
) -> None:
    category = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".menu_categories
        WHERE id = $1 AND outlet_id = $2
        """,
        category_id, outlet_id
    )
    if not category:
        raise HTTPException(404, "Category not found")

    items = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".menu_items
        WHERE category_id = $1 LIMIT 1
        """,
        category_id
    )
    if items:
        raise HTTPException(
            400,
            "Cannot delete category — it has menu items assigned to it"
        )

    await db.execute(
        f'DELETE FROM "{schema}".menu_categories WHERE id = $1',
        category_id
    )


async def create_item(
    db, schema: str, outlet_id: UUID, data: dict
) -> dict:
    # Check menu item limit before creating
    from app.services.subscription_service import check_menu_item_limit
    await check_menu_item_limit(db, schema, outlet_id)

    category = await db.fetchrow(
        f"""
        SELECT id, name FROM "{schema}".menu_categories
        WHERE id = $1 AND outlet_id = $2
        """,
        data["category_id"], outlet_id
    )
    if not category:
        raise HTTPException(400, "Category not found")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".menu_items
            (outlet_id, name, category_id, description, price,
             item_type, tax_rate, station, is_available,
             image_url, sort_order)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING id, name, category_id, description, price,
                  item_type, tax_rate, station, is_available,
                  image_url, sort_order
        """,
        outlet_id,
        data["name"],
        data["category_id"],
        data.get("description"),
        data["price"],
        data.get("item_type", "food"),
        data.get("tax_rate", 13.00),
        data.get("station"),
        data.get("is_available", True),
        data.get("image_url"),
        data.get("sort_order", 0),
    )
    result = dict(row)
    result["category_name"] = category["name"]
    return result


async def list_items(
    db, schema: str, outlet_id: UUID, category_id: UUID = None
) -> list[dict]:
    if category_id:
        rows = await db.fetch(
            f"""
            SELECT i.id, i.name, i.category_id, c.name AS category_name,
                   i.description, i.price, i.item_type, i.tax_rate,
                   i.station, i.is_available, i.image_url, i.sort_order
            FROM "{schema}".menu_items i
            JOIN "{schema}".menu_categories c ON c.id = i.category_id
            WHERE i.outlet_id = $1 AND i.category_id = $2
            ORDER BY i.sort_order, i.name
            """,
            outlet_id, category_id
        )
    else:
        rows = await db.fetch(
            f"""
            SELECT i.id, i.name, i.category_id, c.name AS category_name,
                   i.description, i.price, i.item_type, i.tax_rate,
                   i.station, i.is_available, i.image_url, i.sort_order
            FROM "{schema}".menu_items i
            JOIN "{schema}".menu_categories c ON c.id = i.category_id
            WHERE i.outlet_id = $1
            ORDER BY c.sort_order, i.sort_order, i.name
            """,
            outlet_id
        )
    return [dict(r) for r in rows]


async def get_item(
    db, schema: str, outlet_id: UUID, item_id: UUID
) -> dict:
    row = await db.fetchrow(
        f"""
        SELECT i.id, i.name, i.category_id, c.name AS category_name,
               i.description, i.price, i.item_type, i.tax_rate,
               i.station, i.is_available, i.image_url, i.sort_order
        FROM "{schema}".menu_items i
        JOIN "{schema}".menu_categories c ON c.id = i.category_id
        WHERE i.id = $1 AND i.outlet_id = $2
        """,
        item_id, outlet_id
    )
    if not row:
        raise HTTPException(404, "Menu item not found")
    return dict(row)


async def update_item(
    db, schema: str, outlet_id: UUID,
    item_id: UUID, data: dict
) -> dict:
    item = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".menu_items
        WHERE id = $1 AND outlet_id = $2
        """,
        item_id, outlet_id
    )
    if not item:
        raise HTTPException(404, "Menu item not found")

    if data.get("category_id"):
        cat = await db.fetchrow(
            f"""
            SELECT id FROM "{schema}".menu_categories
            WHERE id = $1 AND outlet_id = $2
            """,
            data["category_id"], outlet_id
        )
        if not cat:
            raise HTTPException(400, "Category not found")

    fields = []
    values = []
    idx = 1
    for field in ["name", "category_id", "description", "price",
                  "item_type", "tax_rate", "station", "is_available",
                  "image_url", "sort_order"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1

    if not fields:
        return await get_item(db, schema, outlet_id, item_id)

    values.append(item_id)
    await db.execute(
        f"""
        UPDATE "{schema}".menu_items
        SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        """,
        *values
    )
    return await get_item(db, schema, outlet_id, item_id)


async def delete_item(
    db, schema: str, outlet_id: UUID, item_id: UUID
) -> None:
    item = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".menu_items
        WHERE id = $1 AND outlet_id = $2
        """,
        item_id, outlet_id
    )
    if not item:
        raise HTTPException(404, "Menu item not found")

    await db.execute(
        f'DELETE FROM "{schema}".menu_items WHERE id = $1',
        item_id
    )