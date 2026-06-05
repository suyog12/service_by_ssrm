from uuid import UUID
from fastapi import HTTPException


# Ingredients 

async def create_ingredient(
    db, schema: str, outlet_id: UUID, data: dict
) -> dict:
    existing = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".ingredients
        WHERE name = $1 AND outlet_id = $2
        """,
        data["name"], outlet_id
    )
    if existing:
        raise HTTPException(
            400, f"An ingredient named '{data['name']}' already exists"
        )

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".ingredients
            (outlet_id, name, unit, reorder_level, cost_per_unit)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, name, unit, reorder_level, current_stock, cost_per_unit
        """,
        outlet_id,
        data["name"],
        data["unit"],
        data.get("reorder_level", 0),
        data.get("cost_per_unit"),
    )
    return dict(row)


async def list_ingredients(
    db, schema: str, outlet_id: UUID
) -> list[dict]:
    rows = await db.fetch(
        f"""
        SELECT id, name, unit, reorder_level, current_stock, cost_per_unit
        FROM "{schema}".ingredients
        WHERE outlet_id = $1
        ORDER BY name
        """,
        outlet_id
    )
    return [dict(r) for r in rows]


async def get_ingredient(
    db, schema: str, outlet_id: UUID, ingredient_id: UUID
) -> dict:
    row = await db.fetchrow(
        f"""
        SELECT id, name, unit, reorder_level, current_stock, cost_per_unit
        FROM "{schema}".ingredients
        WHERE id = $1 AND outlet_id = $2
        """,
        ingredient_id, outlet_id
    )
    if not row:
        raise HTTPException(404, "Ingredient not found")
    return dict(row)


async def update_ingredient(
    db, schema: str, outlet_id: UUID,
    ingredient_id: UUID, data: dict
) -> dict:
    ingredient = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".ingredients
        WHERE id = $1 AND outlet_id = $2
        """,
        ingredient_id, outlet_id
    )
    if not ingredient:
        raise HTTPException(404, "Ingredient not found")

    if data.get("name"):
        existing = await db.fetchrow(
            f"""
            SELECT id FROM "{schema}".ingredients
            WHERE name = $1 AND outlet_id = $2 AND id != $3
            """,
            data["name"], outlet_id, ingredient_id
        )
        if existing:
            raise HTTPException(
                400,
                f"An ingredient named '{data['name']}' already exists"
            )

    fields = []
    values = []
    idx = 1
    for field in ["name", "unit", "reorder_level", "cost_per_unit"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1

    if not fields:
        return await get_ingredient(db, schema, outlet_id, ingredient_id)

    values.append(ingredient_id)
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".ingredients
        SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        RETURNING id, name, unit, reorder_level, current_stock, cost_per_unit
        """,
        *values
    )
    return dict(row)


async def delete_ingredient(
    db, schema: str, outlet_id: UUID, ingredient_id: UUID
) -> None:
    ingredient = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".ingredients
        WHERE id = $1 AND outlet_id = $2
        """,
        ingredient_id, outlet_id
    )
    if not ingredient:
        raise HTTPException(404, "Ingredient not found")

    linked = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".item_ingredients
        WHERE ingredient_id = $1 LIMIT 1
        """,
        ingredient_id
    )
    if linked:
        raise HTTPException(
            400,
            "Cannot delete ingredient — it is linked to one or more menu items"
        )

    await db.execute(
        f'DELETE FROM "{schema}".ingredients WHERE id = $1',
        ingredient_id
    )


# Item ingredient linking 

async def add_ingredient_to_item(
    db, schema: str, outlet_id: UUID, item_id: UUID, data: dict
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

    ingredient = await db.fetchrow(
        f"""
        SELECT id, name, unit FROM "{schema}".ingredients
        WHERE id = $1 AND outlet_id = $2
        """,
        data["ingredient_id"], outlet_id
    )
    if not ingredient:
        raise HTTPException(400, "Ingredient not found")

    existing = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".item_ingredients
        WHERE menu_item_id = $1 AND ingredient_id = $2
        """,
        item_id, data["ingredient_id"]
    )
    if existing:
        raise HTTPException(
            400, "This ingredient is already linked to the item"
        )

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".item_ingredients
            (menu_item_id, ingredient_id, quantity_used)
        VALUES ($1, $2, $3)
        RETURNING id, ingredient_id, quantity_used
        """,
        item_id,
        data["ingredient_id"],
        data["quantity_used"],
    )
    result = dict(row)
    result["ingredient_name"] = ingredient["name"]
    result["unit"] = ingredient["unit"]
    return result


async def list_item_ingredients(
    db, schema: str, outlet_id: UUID, item_id: UUID
) -> list[dict]:
    item = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".menu_items
        WHERE id = $1 AND outlet_id = $2
        """,
        item_id, outlet_id
    )
    if not item:
        raise HTTPException(404, "Menu item not found")

    rows = await db.fetch(
        f"""
        SELECT ii.id, ii.ingredient_id, i.name AS ingredient_name,
               i.unit, ii.quantity_used
        FROM "{schema}".item_ingredients ii
        JOIN "{schema}".ingredients i ON i.id = ii.ingredient_id
        WHERE ii.menu_item_id = $1
        ORDER BY i.name
        """,
        item_id
    )
    return [dict(r) for r in rows]


async def update_item_ingredient(
    db, schema: str, outlet_id: UUID,
    item_id: UUID, ingredient_id: UUID, data: dict
) -> dict:
    link = await db.fetchrow(
        f"""
        SELECT ii.id, i.name AS ingredient_name, i.unit
        FROM "{schema}".item_ingredients ii
        JOIN "{schema}".ingredients i ON i.id = ii.ingredient_id
        WHERE ii.menu_item_id = $1 AND ii.ingredient_id = $2
        """,
        item_id, ingredient_id
    )
    if not link:
        raise HTTPException(404, "Ingredient link not found")

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".item_ingredients
        SET quantity_used = $1
        WHERE menu_item_id = $2 AND ingredient_id = $3
        RETURNING id, ingredient_id, quantity_used
        """,
        data["quantity_used"], item_id, ingredient_id
    )
    result = dict(row)
    result["ingredient_name"] = link["ingredient_name"]
    result["unit"] = link["unit"]
    return result


async def remove_ingredient_from_item(
    db, schema: str, outlet_id: UUID,
    item_id: UUID, ingredient_id: UUID
) -> None:
    link = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".item_ingredients
        WHERE menu_item_id = $1 AND ingredient_id = $2
        """,
        item_id, ingredient_id
    )
    if not link:
        raise HTTPException(404, "Ingredient link not found")

    await db.execute(
        f"""
        DELETE FROM "{schema}".item_ingredients
        WHERE menu_item_id = $1 AND ingredient_id = $2
        """,
        item_id, ingredient_id
    )