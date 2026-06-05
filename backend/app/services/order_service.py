from uuid import UUID
from fastapi import HTTPException
import secrets
import string


def _generate_order_number() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(6))
    return f"ORD-{suffix}"


# Orders 

async def create_order(
    db, schema: str, outlet_id: UUID, data: dict, taken_by: UUID
) -> dict:
    table_number = None
    if data.get("table_id"):
        table = await db.fetchrow(
            f"""
            SELECT id, table_number, status FROM "{schema}".tables
            WHERE id = $1 AND outlet_id = $2
            """,
            data["table_id"], outlet_id
        )
        if not table:
            raise HTTPException(400, "Table not found")
        if table["status"] == "occupied":
            raise HTTPException(400, "Table is already occupied")
        table_number = table["table_number"]

        await db.execute(
            f"""
            UPDATE "{schema}".tables
            SET status = $1, updated_at = NOW()
            WHERE id = $2
            """,
            "occupied", data["table_id"]
        )

    for _ in range(10):
        order_number = _generate_order_number()
        existing = await db.fetchrow(
            f'SELECT id FROM "{schema}".orders WHERE order_number = $1',
            order_number
        )
        if not existing:
            break

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".orders
            (outlet_id, order_number, order_type, table_id,
             customer_id, taken_by, notes)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id, order_number, order_type, status,
                  table_id, notes
        """,
        outlet_id,
        order_number,
        data.get("order_type", "dine_in"),
        data.get("table_id"),
        data.get("customer_id"),
        taken_by,
        data.get("notes"),
    )
    result = dict(row)
    result["table_number"] = table_number
    result["item_count"] = 0
    return result


async def list_orders(
    db, schema: str, outlet_id: UUID, status: str = None
) -> list[dict]:
    if status:
        rows = await db.fetch(
            f"""
            SELECT o.id, o.order_number, o.order_type, o.status,
                   o.table_id, t.table_number, o.notes,
                   COUNT(oi.id) AS item_count
            FROM "{schema}".orders o
            LEFT JOIN "{schema}".tables t ON t.id = o.table_id
            LEFT JOIN "{schema}".order_items oi ON oi.order_id = o.id
            WHERE o.outlet_id = $1 AND o.status = $2
            GROUP BY o.id, t.table_number
            ORDER BY o.created_at DESC
            """,
            outlet_id, status
        )
    else:
        rows = await db.fetch(
            f"""
            SELECT o.id, o.order_number, o.order_type, o.status,
                   o.table_id, t.table_number, o.notes,
                   COUNT(oi.id) AS item_count
            FROM "{schema}".orders o
            LEFT JOIN "{schema}".tables t ON t.id = o.table_id
            LEFT JOIN "{schema}".order_items oi ON oi.order_id = o.id
            WHERE o.outlet_id = $1
            GROUP BY o.id, t.table_number
            ORDER BY o.created_at DESC
            """,
            outlet_id
        )
    return [dict(r) for r in rows]


async def get_order(
    db, schema: str, outlet_id: UUID, order_id: UUID
) -> dict:
    row = await db.fetchrow(
        f"""
        SELECT o.id, o.order_number, o.order_type, o.status,
               o.table_id, t.table_number, o.notes,
               COUNT(oi.id) AS item_count
        FROM "{schema}".orders o
        LEFT JOIN "{schema}".tables t ON t.id = o.table_id
        LEFT JOIN "{schema}".order_items oi ON oi.order_id = o.id
        WHERE o.id = $1 AND o.outlet_id = $2
        GROUP BY o.id, t.table_number
        """,
        order_id, outlet_id
    )
    if not row:
        raise HTTPException(404, "Order not found")
    return dict(row)


async def update_order_status(
    db, schema: str, outlet_id: UUID,
    order_id: UUID, new_status: str, changed_by: UUID
) -> dict:
    order = await db.fetchrow(
        f"""
        SELECT id, status, table_id FROM "{schema}".orders
        WHERE id = $1 AND outlet_id = $2
        """,
        order_id, outlet_id
    )
    if not order:
        raise HTTPException(404, "Order not found")
    if order["status"] == "cancelled":
        raise HTTPException(400, "Cannot update a cancelled order")
    if order["status"] == "billed":
        raise HTTPException(400, "Cannot update a billed order")

    await db.execute(
        f"""
        INSERT INTO "{schema}".order_status_log
            (order_id, from_status, to_status, changed_by)
        VALUES ($1, $2, $3, $4)
        """,
        order_id, order["status"], new_status, changed_by
    )

    await db.execute(
        f"""
        UPDATE "{schema}".orders
        SET status = $1, updated_at = NOW()
        WHERE id = $2
        """,
        new_status, order_id
    )

    if new_status in ("cancelled", "billed") and order["table_id"]:
        await db.execute(
            f"""
            UPDATE "{schema}".tables
            SET status = $1, updated_at = NOW()
            WHERE id = $2
            """,
            "available", order["table_id"]
        )

    return await get_order(db, schema, outlet_id, order_id)


# Order items 

async def add_item_to_order(
    db, schema: str, outlet_id: UUID,
    order_id: UUID, data: dict
) -> dict:
    order = await db.fetchrow(
        f"""
        SELECT id, status FROM "{schema}".orders
        WHERE id = $1 AND outlet_id = $2
        """,
        order_id, outlet_id
    )
    if not order:
        raise HTTPException(404, "Order not found")
    if order["status"] in ("billed", "cancelled"):
        raise HTTPException(400, "Cannot add items to a closed order")

    menu_item = await db.fetchrow(
        f"""
        SELECT id, name, price, station, is_available
        FROM "{schema}".menu_items
        WHERE id = $1 AND outlet_id = $2
        """,
        data["menu_item_id"], outlet_id
    )
    if not menu_item:
        raise HTTPException(400, "Menu item not found")
    if not menu_item["is_available"]:
        raise HTTPException(400, "Menu item is not currently available")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".order_items
            (order_id, menu_item_id, quantity, unit_price,
             special_instruction, station)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, order_id, menu_item_id, quantity, unit_price,
                  special_instruction, status, station
        """,
        order_id,
        data["menu_item_id"],
        data.get("quantity", 1),
        menu_item["price"],
        data.get("special_instruction"),
        menu_item["station"],
    )
    result = dict(row)
    result["item_name"] = menu_item["name"]

    if order["status"] == "open":
        await db.execute(
            f"""
            UPDATE "{schema}".orders
            SET status = $1, updated_at = NOW()
            WHERE id = $2
            """,
            "in_progress", order_id
        )

    return result


async def list_order_items(
    db, schema: str, outlet_id: UUID, order_id: UUID
) -> list[dict]:
    order = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".orders
        WHERE id = $1 AND outlet_id = $2
        """,
        order_id, outlet_id
    )
    if not order:
        raise HTTPException(404, "Order not found")

    rows = await db.fetch(
        f"""
        SELECT oi.id, oi.order_id, oi.menu_item_id, mi.name AS item_name,
               oi.quantity, oi.unit_price, oi.special_instruction,
               oi.status, oi.station
        FROM "{schema}".order_items oi
        JOIN "{schema}".menu_items mi ON mi.id = oi.menu_item_id
        WHERE oi.order_id = $1
        ORDER BY oi.created_at
        """,
        order_id
    )
    return [dict(r) for r in rows]


async def update_item_status(
    db, schema: str, outlet_id: UUID,
    order_id: UUID, item_id: UUID, new_status: str
) -> dict:
    item = await db.fetchrow(
        f"""
        SELECT oi.id, oi.status, oi.menu_item_id, oi.quantity,
               mi.name AS item_name, oi.unit_price,
               oi.special_instruction, oi.station
        FROM "{schema}".order_items oi
        JOIN "{schema}".menu_items mi ON mi.id = oi.menu_item_id
        WHERE oi.id = $1 AND oi.order_id = $2
        """,
        item_id, order_id
    )
    if not item:
        raise HTTPException(404, "Order item not found")
    if item["status"] == "cancelled":
        raise HTTPException(400, "Cannot update a cancelled item")

    # Verify order belongs to outlet
    order = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".orders
        WHERE id = $1 AND outlet_id = $2
        """,
        order_id, outlet_id
    )
    if not order:
        raise HTTPException(404, "Order not found")

    await db.execute(
        f"""
        UPDATE "{schema}".order_items
        SET status = $1, updated_at = NOW()
        WHERE id = $2
        """,
        new_status, item_id
    )

    if new_status == "served":
        await _deduct_stock(
            db, schema, item["menu_item_id"], item["quantity"], item_id
        )

    result = dict(item)
    result["status"] = new_status
    result["order_id"] = order_id
    return result


async def cancel_order_item(
    db, schema: str, outlet_id: UUID,
    order_id: UUID, item_id: UUID
) -> dict:
    return await update_item_status(
        db, schema, outlet_id, order_id, item_id, "cancelled"
    )


async def _deduct_stock(
    db, schema: str, menu_item_id: UUID,
    quantity: int, order_item_id: UUID
) -> None:
    ingredients = await db.fetch(
        f"""
        SELECT ingredient_id, quantity_used
        FROM "{schema}".item_ingredients
        WHERE menu_item_id = $1
        """,
        menu_item_id
    )
    for ing in ingredients:
        total_used = ing["quantity_used"] * quantity
        await db.execute(
            f"""
            UPDATE "{schema}".ingredients
            SET current_stock = GREATEST(0, current_stock - $1),
                updated_at = NOW()
            WHERE id = $2
            """,
            total_used, ing["ingredient_id"]
        )
        await db.execute(
            f"""
            INSERT INTO "{schema}".stock_deductions
                (ingredient_id, order_item_id, quantity_used)
            VALUES ($1, $2, $3)
            """,
            ing["ingredient_id"], order_item_id, total_used
        )