from uuid import UUID
from fastapi import HTTPException
from decimal import Decimal
import secrets
import string
from app.utils.email import send_email


VALID_PO_STATUSES = (
    "draft", "pending_approval", "approved", "sent",
    "partial", "received", "cancelled"
)


def _generate_po_number() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(6))
    return f"PO-{suffix}"


async def _fire_low_stock_alert(db, schema: str, ingredient_id: UUID):
    ingredient = await db.fetchrow(
        f"""
        SELECT name, unit, current_stock, reorder_level
        FROM "{schema}".ingredients
        WHERE id = $1
        """,
        ingredient_id
    )
    if not ingredient:
        return
    if Decimal(str(ingredient["current_stock"])) > Decimal(str(ingredient["reorder_level"])):
        return

    # Get all admin users for this tenant
    tenant = await db.fetchrow(
        'SELECT id FROM core.tenants WHERE schema_name = $1', schema
    )
    if not tenant:
        return

    admins = await db.fetch(
        'SELECT id, email, full_name FROM core.users WHERE tenant_id = $1 AND is_admin = TRUE AND is_active = TRUE',
        tenant["id"]
    )

    title = f"Low stock alert: {ingredient['name']}"
    body = (
        f"{ingredient['name']} is running low. "
        f"Current stock: {ingredient['current_stock']} {ingredient['unit']}. "
        f"Reorder level: {ingredient['reorder_level']} {ingredient['unit']}."
    )

    for admin in admins:
        await db.execute(
            f"""
            INSERT INTO "{schema}".notifications
                (user_id, event_code, title, body, reference_id, reference_type)
            VALUES ($1, 'inventory.low_stock', $2, $3, $4, 'ingredient')
            """,
            admin["id"], title, body, ingredient_id
        )
        try:
            await send_email(
                to=admin["email"],
                subject=title,
                body=body
            )
        except Exception:
            pass


# Suppliers 

async def create_supplier(db, schema: str, data: dict) -> dict:
    existing = await db.fetchrow(
        f'SELECT id FROM "{schema}".suppliers WHERE name = $1',
        data["name"]
    )
    if existing:
        raise HTTPException(400, "A supplier with this name already exists")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".suppliers
            (name, contact_person, phone, email, address, pan_number)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        data["name"],
        data.get("contact_person"),
        data.get("phone"),
        data.get("email"),
        data.get("address"),
        data.get("pan_number"),
    )
    return dict(row)


async def list_suppliers(db, schema: str, active_only: bool = False) -> list[dict]:
    if active_only:
        rows = await db.fetch(
            f'SELECT * FROM "{schema}".suppliers WHERE is_active = TRUE ORDER BY name'
        )
    else:
        rows = await db.fetch(
            f'SELECT * FROM "{schema}".suppliers ORDER BY name'
        )
    return [dict(r) for r in rows]


async def get_supplier(db, schema: str, supplier_id: UUID) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".suppliers WHERE id = $1',
        supplier_id
    )
    if not row:
        raise HTTPException(404, "Supplier not found")
    return dict(row)


async def update_supplier(db, schema: str, supplier_id: UUID, data: dict) -> dict:
    await get_supplier(db, schema, supplier_id)

    fields = []
    values = []
    idx = 1
    for field in ["name", "contact_person", "phone", "email",
                  "address", "pan_number", "is_active"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1

    if not fields:
        return await get_supplier(db, schema, supplier_id)

    values.append(supplier_id)
    await db.execute(
        f"""
        UPDATE "{schema}".suppliers
        SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        """,
        *values
    )
    return await get_supplier(db, schema, supplier_id)


# Stock Addition 

async def add_stock(db, schema: str, data: dict) -> dict:
    ingredient = await db.fetchrow(
        f'SELECT id, name, unit, current_stock FROM "{schema}".ingredients WHERE id = $1',
        data["ingredient_id"]
    )
    if not ingredient:
        raise HTTPException(404, "Ingredient not found")

    quantity = Decimal(str(data["quantity"]))

    # Update cost_per_unit if provided
    if data.get("cost_per_unit") is not None:
        await db.execute(
            f"""
            UPDATE "{schema}".ingredients
            SET cost_per_unit = $1, updated_at = NOW()
            WHERE id = $2
            """,
            data["cost_per_unit"], data["ingredient_id"]
        )

    # Create stock batch
    batch = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".stock_batches
            (ingredient_id, quantity, remaining, expiry_date, notes)
        VALUES ($1, $2, $2, $3, $4)
        RETURNING id
        """,
        data["ingredient_id"],
        quantity,
        data.get("expiry_date"),
        data.get("notes"),
    )

    # Update current stock
    new_stock = Decimal(str(ingredient["current_stock"])) + quantity
    await db.execute(
        f"""
        UPDATE "{schema}".ingredients
        SET current_stock = $1, updated_at = NOW()
        WHERE id = $2
        """,
        new_stock, data["ingredient_id"]
    )

    return {
        "ingredient_id": data["ingredient_id"],
        "ingredient_name": ingredient["name"],
        "unit": ingredient["unit"],
        "quantity_added": quantity,
        "current_stock": new_stock,
        "batch_id": batch["id"],
    }


# Stock Adjustments 

async def adjust_stock(db, schema: str, data: dict, adjusted_by: UUID) -> dict:
    ingredient = await db.fetchrow(
        f'SELECT id, name, unit, current_stock FROM "{schema}".ingredients WHERE id = $1',
        data["ingredient_id"]
    )
    if not ingredient:
        raise HTTPException(404, "Ingredient not found")

    previous_stock = Decimal(str(ingredient["current_stock"]))
    new_stock = Decimal(str(data["new_stock"]))

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".stock_adjustments
            (ingredient_id, adjusted_by, previous_stock, new_stock, reason)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, ingredient_id, adjusted_by, previous_stock, new_stock, reason, created_at
        """,
        data["ingredient_id"],
        adjusted_by,
        previous_stock,
        new_stock,
        data["reason"],
    )

    await db.execute(
        f"""
        UPDATE "{schema}".ingredients
        SET current_stock = $1, updated_at = NOW()
        WHERE id = $2
        """,
        new_stock, data["ingredient_id"]
    )

    # Notify admins about the adjustment
    tenant = await db.fetchrow(
        'SELECT id FROM core.tenants WHERE schema_name = $1', schema
    )
    if tenant:
        admins = await db.fetch(
            'SELECT id FROM core.users WHERE tenant_id = $1 AND is_admin = TRUE AND is_active = TRUE',
            tenant["id"]
        )
        title = f"Stock adjusted: {ingredient['name']}"
        body = (
            f"Stock for {ingredient['name']} was manually adjusted "
            f"from {previous_stock} to {new_stock} {ingredient['unit']}. "
            f"Reason: {data['reason']}"
        )
        for admin in admins:
            await db.execute(
                f"""
                INSERT INTO "{schema}".notifications
                    (user_id, event_code, title, body, reference_id, reference_type)
                VALUES ($1, 'inventory.stock_adjusted', $2, $3, $4, 'ingredient')
                """,
                admin["id"], title, body, data["ingredient_id"]
            )

    # Check low stock after adjustment
    await _fire_low_stock_alert(db, schema, data["ingredient_id"])

    result = dict(row)
    result["ingredient_name"] = ingredient["name"]
    result["unit"] = ingredient["unit"]
    return result


async def list_stock_adjustments(db, schema: str, ingredient_id: UUID = None) -> list[dict]:
    if ingredient_id:
        rows = await db.fetch(
            f"""
            SELECT sa.*, i.name AS ingredient_name, i.unit
            FROM "{schema}".stock_adjustments sa
            JOIN "{schema}".ingredients i ON i.id = sa.ingredient_id
            WHERE sa.ingredient_id = $1
            ORDER BY sa.created_at DESC
            """,
            ingredient_id
        )
    else:
        rows = await db.fetch(
            f"""
            SELECT sa.*, i.name AS ingredient_name, i.unit
            FROM "{schema}".stock_adjustments sa
            JOIN "{schema}".ingredients i ON i.id = sa.ingredient_id
            ORDER BY sa.created_at DESC
            """
        )
    return [dict(r) for r in rows]


# Reorder Alerts 

async def get_reorder_alerts(db, schema: str) -> list[dict]:
    rows = await db.fetch(
        f"""
        SELECT id AS ingredient_id, name AS ingredient_name,
               unit, current_stock, reorder_level
        FROM "{schema}".ingredients
        WHERE current_stock <= reorder_level
          AND reorder_level > 0
        ORDER BY name
        """
    )
    return [dict(r) for r in rows]


# Purchase Orders 

async def _get_po_with_items(db, schema: str, po_id: UUID) -> dict:
    po = await db.fetchrow(
        f"""
        SELECT po.*, s.name AS supplier_name
        FROM "{schema}".purchase_orders po
        JOIN "{schema}".suppliers s ON s.id = po.supplier_id
        WHERE po.id = $1
        """,
        po_id
    )
    if not po:
        raise HTTPException(404, "Purchase order not found")

    items = await db.fetch(
        f"""
        SELECT pi.*, i.name AS ingredient_name, i.unit
        FROM "{schema}".po_items pi
        JOIN "{schema}".ingredients i ON i.id = pi.ingredient_id
        WHERE pi.po_id = $1
        ORDER BY i.name
        """,
        po_id
    )

    result = dict(po)
    result["items"] = [dict(i) for i in items]
    return result


async def create_purchase_order(
    db, schema: str, data: dict, raised_by: UUID
) -> dict:
    supplier = await db.fetchrow(
        f'SELECT id, is_active FROM "{schema}".suppliers WHERE id = $1',
        data["supplier_id"]
    )
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    if not supplier["is_active"]:
        raise HTTPException(400, "Supplier is inactive")

    for _ in range(10):
        po_number = _generate_po_number()
        existing = await db.fetchrow(
            f'SELECT id FROM "{schema}".purchase_orders WHERE po_number = $1',
            po_number
        )
        if not existing:
            break

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".purchase_orders
            (supplier_id, po_number, raised_by, expected_date, notes)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        data["supplier_id"],
        po_number,
        raised_by,
        data.get("expected_date"),
        data.get("notes"),
    )
    return await _get_po_with_items(db, schema, row["id"])


async def add_po_item(
    db, schema: str, po_id: UUID, data: dict
) -> dict:
    po = await db.fetchrow(
        f'SELECT id, status FROM "{schema}".purchase_orders WHERE id = $1',
        po_id
    )
    if not po:
        raise HTTPException(404, "Purchase order not found")
    if po["status"] not in ("draft",):
        raise HTTPException(400, "Can only add items to a draft purchase order")

    ingredient = await db.fetchrow(
        f'SELECT id FROM "{schema}".ingredients WHERE id = $1',
        data["ingredient_id"]
    )
    if not ingredient:
        raise HTTPException(404, "Ingredient not found")

    existing_item = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".po_items
        WHERE po_id = $1 AND ingredient_id = $2
        """,
        po_id, data["ingredient_id"]
    )
    if existing_item:
        raise HTTPException(400, "This ingredient is already on the purchase order")

    await db.execute(
        f"""
        INSERT INTO "{schema}".po_items
            (po_id, ingredient_id, ordered_qty, unit_price, notes)
        VALUES ($1, $2, $3, $4, $5)
        """,
        po_id,
        data["ingredient_id"],
        data["ordered_qty"],
        data.get("unit_price"),
        data.get("notes"),
    )

    await _recalculate_po_total(db, schema, po_id)
    return await _get_po_with_items(db, schema, po_id)


async def _recalculate_po_total(db, schema: str, po_id: UUID):
    total = await db.fetchval(
        f"""
        SELECT COALESCE(SUM(ordered_qty * unit_price), 0)
        FROM "{schema}".po_items
        WHERE po_id = $1 AND unit_price IS NOT NULL
        """,
        po_id
    )
    await db.execute(
        f"""
        UPDATE "{schema}".purchase_orders
        SET total_amount = $1, updated_at = NOW()
        WHERE id = $2
        """,
        total, po_id
    )


async def list_purchase_orders(db, schema: str, status: str = None) -> list[dict]:
    if status:
        rows = await db.fetch(
            f"""
            SELECT po.*, s.name AS supplier_name
            FROM "{schema}".purchase_orders po
            JOIN "{schema}".suppliers s ON s.id = po.supplier_id
            WHERE po.status = $1
            ORDER BY po.created_at DESC
            """,
            status
        )
    else:
        rows = await db.fetch(
            f"""
            SELECT po.*, s.name AS supplier_name
            FROM "{schema}".purchase_orders po
            JOIN "{schema}".suppliers s ON s.id = po.supplier_id
            ORDER BY po.created_at DESC
            """
        )
    result = []
    for row in rows:
        d = dict(row)
        items = await db.fetch(
            f"""
            SELECT pi.*, i.name AS ingredient_name, i.unit
            FROM "{schema}".po_items pi
            JOIN "{schema}".ingredients i ON i.id = pi.ingredient_id
            WHERE pi.po_id = $1
            """,
            d["id"]
        )
        d["items"] = [dict(i) for i in items]
        result.append(d)
    return result


async def get_purchase_order(db, schema: str, po_id: UUID) -> dict:
    return await _get_po_with_items(db, schema, po_id)


async def update_po_status(
    db, schema: str, po_id: UUID, new_status: str, user_id: UUID
) -> dict:
    po = await db.fetchrow(
        f'SELECT id, status FROM "{schema}".purchase_orders WHERE id = $1',
        po_id
    )
    if not po:
        raise HTTPException(404, "Purchase order not found")

    current = po["status"]

    valid_transitions = {
        "draft": ("pending_approval", "cancelled"),
        "pending_approval": ("approved", "cancelled"),
        "approved": ("sent", "cancelled"),
        "sent": ("received", "partial", "cancelled"),
        "partial": ("received", "cancelled"),
    }

    allowed = valid_transitions.get(current, ())
    if new_status not in allowed:
        raise HTTPException(
            400,
            f"Cannot move from '{current}' to '{new_status}'"
        )

    update_fields = "status = $1, updated_at = NOW()"
    values = [new_status]

    if new_status == "approved":
        update_fields += ", approved_by = $2, approved_at = NOW()"
        values.append(user_id)
        values.append(po_id)
    elif new_status == "sent":
        update_fields += ", sent_at = NOW()"
        values.append(po_id)
    else:
        values.append(po_id)

    idx = len(values)
    await db.execute(
        f"""
        UPDATE "{schema}".purchase_orders
        SET {update_fields}
        WHERE id = ${idx}
        """,
        *values
    )
    return await _get_po_with_items(db, schema, po_id)


async def receive_purchase_order(
    db, schema: str, po_id: UUID, items: list[dict], received_by: UUID
) -> dict:
    po = await db.fetchrow(
        f'SELECT id, status FROM "{schema}".purchase_orders WHERE id = $1',
        po_id
    )
    if not po:
        raise HTTPException(404, "Purchase order not found")
    if po["status"] not in ("approved", "sent", "partial"):
        raise HTTPException(
            400, "Can only receive approved, sent, or partially received orders"
        )

    for item_data in items:
        po_item = await db.fetchrow(
            f"""
            SELECT pi.*, i.id AS ing_id
            FROM "{schema}".po_items pi
            JOIN "{schema}".ingredients i ON i.id = pi.ingredient_id
            WHERE pi.id = $1 AND pi.po_id = $2
            """,
            item_data["po_item_id"], po_id
        )
        if not po_item:
            raise HTTPException(
                400, f"PO item {item_data['po_item_id']} not found on this order"
            )

        received_qty = Decimal(str(item_data["received_qty"]))
        rejected_qty = Decimal(str(item_data.get("rejected_qty", 0)))

        await db.execute(
            f"""
            UPDATE "{schema}".po_items
            SET received_qty = received_qty + $1,
                rejected_qty = rejected_qty + $2
            WHERE id = $3
            """,
            received_qty, rejected_qty, item_data["po_item_id"]
        )

        if received_qty > 0:
            # Create stock batch
            await db.execute(
                f"""
                INSERT INTO "{schema}".stock_batches
                    (ingredient_id, quantity, remaining, expiry_date)
                VALUES ($1, $2, $2, $3)
                """,
                po_item["ing_id"],
                received_qty,
                item_data.get("expiry_date"),
            )

            # Update current stock
            await db.execute(
                f"""
                UPDATE "{schema}".ingredients
                SET current_stock = current_stock + $1, updated_at = NOW()
                WHERE id = $2
                """,
                received_qty, po_item["ing_id"]
            )

            # Check low stock
            await _fire_low_stock_alert(db, schema, po_item["ing_id"])

    # Determine new PO status
    all_items = await db.fetch(
        f"""
        SELECT ordered_qty, received_qty
        FROM "{schema}".po_items
        WHERE po_id = $1
        """,
        po_id
    )

    all_received = all(
        Decimal(str(i["received_qty"])) >= Decimal(str(i["ordered_qty"]))
        for i in all_items
    )
    any_received = any(
        Decimal(str(i["received_qty"])) > 0
        for i in all_items
    )

    if all_received:
        new_status = "received"
    elif any_received:
        new_status = "partial"
    else:
        new_status = po["status"]

    await db.execute(
        f"""
        UPDATE "{schema}".purchase_orders
        SET status = $1, updated_at = NOW()
        WHERE id = $2
        """,
        new_status, po_id
    )

    return await _get_po_with_items(db, schema, po_id)