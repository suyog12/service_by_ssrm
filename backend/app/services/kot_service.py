from uuid import UUID
from fastapi import HTTPException
from datetime import datetime, timezone
import secrets
import string


def _generate_kot_number(order_number: str, kot_type: str) -> str:
    suffix = kot_type[0].upper()
    return f"{order_number}-{suffix}"


async def generate_kots_for_order(db, schema: str, order_id: UUID) -> list[dict]:
    order = await db.fetchrow(
        f'SELECT id, order_number FROM "{schema}".orders WHERE id = $1',
        order_id
    )
    if not order:
        raise HTTPException(404, "Order not found")

    items = await db.fetch(
        f"""
        SELECT oi.id, oi.quantity, oi.special_instruction,
               mi.name AS item_name, mi.item_type, mi.station
        FROM "{schema}".order_items oi
        JOIN "{schema}".menu_items mi ON mi.id = oi.menu_item_id
        WHERE oi.order_id = $1 AND oi.status = 'pending'
        """,
        order_id
    )

    if not items:
        return []

    food_items = [i for i in items if i["item_type"] in ("food", "both")]
    drink_items = [i for i in items if i["item_type"] in ("drinks", "both")]

    kots = []

    for kot_type, kot_items in [("food", food_items), ("drinks", drink_items)]:
        if not kot_items:
            continue

        kot_number = _generate_kot_number(order["order_number"], kot_type)

        existing = await db.fetchrow(
            f"""
            SELECT id FROM "{schema}".kots
            WHERE order_id = $1 AND kot_type = $2
            """,
            order_id, kot_type
        )
        if existing:
            continue

        row = await db.fetchrow(
            f"""
            INSERT INTO "{schema}".kots
                (order_id, kot_number, kot_type)
            VALUES ($1, $2, $3)
            RETURNING id, order_id, kot_number, kot_type,
                      display_status, assigned_to, printed_at, created_at
            """,
            order_id, kot_number, kot_type
        )
        kots.append(dict(row))

        for item in kot_items:
            await db.execute(
                f"""
                UPDATE "{schema}".order_items
                SET status = 'preparing', updated_at = NOW()
                WHERE id = $1
                """,
                item["id"]
            )

    return kots


async def get_order_kots(db, schema: str, order_id: UUID) -> list[dict]:
    order = await db.fetchrow(
        f'SELECT id FROM "{schema}".orders WHERE id = $1',
        order_id
    )
    if not order:
        raise HTTPException(404, "Order not found")

    rows = await db.fetch(
        f"""
        SELECT id, order_id, kot_number, kot_type,
               display_status, assigned_to, printed_at, created_at
        FROM "{schema}".kots
        WHERE order_id = $1
        ORDER BY created_at
        """,
        order_id
    )
    return [dict(r) for r in rows]


async def get_pending_kots(db, schema: str) -> list[dict]:
    rows = await db.fetch(
        f"""
        SELECT k.id, k.order_id, k.kot_number, k.kot_type,
               k.display_status, k.assigned_to, k.printed_at, k.created_at,
               o.order_number, o.table_id, t.table_number
        FROM "{schema}".kots k
        JOIN "{schema}".orders o ON o.id = k.order_id
        LEFT JOIN "{schema}".tables t ON t.id = o.table_id
        WHERE k.display_status IN ('pending', 'assigned', 'preparing')
        ORDER BY k.created_at
        """
    )
    return [dict(r) for r in rows]


async def assign_kot(
    db, schema: str, kot_id: UUID, assigned_to: UUID
) -> dict:
    kot = await db.fetchrow(
        f'SELECT id, display_status FROM "{schema}".kots WHERE id = $1',
        kot_id
    )
    if not kot:
        raise HTTPException(404, "KOT not found")
    if kot["display_status"] == "done":
        raise HTTPException(400, "KOT is already done")

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".kots
        SET assigned_to = $1, display_status = 'assigned'
        WHERE id = $2
        RETURNING id, order_id, kot_number, kot_type,
                  display_status, assigned_to, printed_at, created_at
        """,
        assigned_to, kot_id
    )
    return dict(row)


async def mark_kot_printed(db, schema: str, kot_id: UUID) -> dict:
    kot = await db.fetchrow(
        f'SELECT id FROM "{schema}".kots WHERE id = $1',
        kot_id
    )
    if not kot:
        raise HTTPException(404, "KOT not found")

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".kots
        SET printed_at = NOW()
        WHERE id = $1
        RETURNING id, order_id, kot_number, kot_type,
                  display_status, assigned_to, printed_at, created_at
        """,
        kot_id
    )
    return dict(row)


async def get_kot_html(db, schema: str, kot_id: UUID) -> str:
    kot = await db.fetchrow(
        f"""
        SELECT k.id, k.kot_number, k.kot_type, k.created_at,
               o.order_number, o.order_type, o.notes,
               t.table_number,
               tn.name AS biz_name
        FROM "{schema}".kots k
        JOIN "{schema}".orders o  ON o.id = k.order_id
        LEFT JOIN "{schema}".tables t ON t.id = o.table_id
        LEFT JOIN core.tenants tn ON tn.schema_name = $2
        WHERE k.id = $1
        """,
        kot_id, schema
    )
    if not kot:
        raise HTTPException(404, "KOT not found")

    items = await db.fetch(
        f"""
        SELECT oi.quantity, oi.special_instruction,
               mi.name AS item_name, mi.station
        FROM "{schema}".order_items oi
        JOIN "{schema}".menu_items mi ON mi.id = oi.menu_item_id
        WHERE oi.order_id = (
            SELECT order_id FROM "{schema}".kots WHERE id = $1
        )
        AND mi.item_type = $2
        AND oi.status != 'cancelled'
        ORDER BY oi.created_at
        """,
        kot_id,
        kot["kot_type"]
    )

    biz_name = kot["biz_name"] or "Restaurant"

    if kot["table_number"]:
        table_info = f"Table: {kot['table_number']}"
    elif kot["order_type"]:
        table_info = kot["order_type"].replace("_", " ").title()
    else:
        table_info = ""

    created_time = kot["created_at"].strftime("%Y-%m-%d %H:%M") if kot["created_at"] else ""

    items_html = ""
    for item in items:
        instruction = (
            f"<div class='instruction'>* {item['special_instruction']}</div>"
            if item["special_instruction"] else ""
        )
        station = (
            f"<span class='station'>[{item['station'].upper()}]</span>"
            if item["station"] else ""
        )
        items_html += f"""
        <div class='item'>
            <div class='item-main'>
                <span class='qty'>{item['quantity']}x</span>
                <span class='name'>{item['item_name']}</span>
                {station}
            </div>
            {instruction}
        </div>
        """

    if kot["kot_type"] == "food":
        kot_type_label = "KITCHEN ORDER"
        copy_label = "KITCHEN COPY"
    else:
        kot_type_label = "BAR ORDER"
        copy_label = "BAR COPY"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: 'Courier New', monospace;
        width: 80mm;
        padding: 8px;
        font-size: 13px;
    }}
    .biz-name {{
        text-align: center;
        font-size: 13px;
        font-weight: bold;
        margin-bottom: 3px;
    }}
    .header {{
        text-align: center;
        border-bottom: 1px dashed #000;
        padding-bottom: 8px;
        margin-bottom: 6px;
    }}
    .divider {{
        border: none;
        border-top: 1px dashed #ccc;
        margin: 5px 0;
    }}
    .kot-type {{
        font-size: 17px;
        font-weight: bold;
        letter-spacing: 2px;
        margin: 4px 0 2px;
    }}
    .kot-number {{
        font-size: 14px;
        font-weight: bold;
        margin: 3px 0;
    }}
    .meta {{
        font-size: 11px;
        color: #333;
        margin: 2px 0;
    }}
    .items {{
        margin: 8px 0;
        border-top: 1px dashed #000;
        padding-top: 8px;
    }}
    .item {{
        margin: 8px 0;
    }}
    .item-main {{
        display: flex;
        align-items: baseline;
        gap: 6px;
    }}
    .qty {{
        font-size: 18px;
        font-weight: bold;
        min-width: 32px;
    }}
    .name {{
        font-size: 14px;
        font-weight: bold;
        flex: 1;
    }}
    .station {{
        font-size: 10px;
        color: #555;
    }}
    .instruction {{
        font-size: 11px;
        color: #444;
        padding-left: 38px;
        font-style: italic;
        margin-top: 2px;
    }}
    .footer {{
        text-align: center;
        border-top: 1px dashed #000;
        padding-top: 6px;
        margin-top: 8px;
        font-size: 11px;
        color: #333;
    }}
    .copy-label {{
        font-size: 12px;
        font-weight: bold;
        letter-spacing: 1px;
        margin-top: 3px;
    }}
</style>
</head>
<body>
    <div class='header'>
        <div class='biz-name'>{biz_name}</div>
        <hr class='divider'>
        <div class='kot-type'>{kot_type_label}</div>
        <div class='kot-number'>{kot['kot_number']}</div>
        <div class='meta'>{table_info}</div>
        <div class='meta'>{created_time}</div>
        {f"<div class='meta' style='margin-top:4px;font-style:italic;'>Note: {kot['notes']}</div>" if kot['notes'] else ""}
    </div>
    <div class='items'>
        {items_html}
    </div>
    <div class='footer'>
        Order: {kot['order_number']}
        <div class='copy-label'>— {copy_label} —</div>
    </div>
</body>
</html>"""

    return html