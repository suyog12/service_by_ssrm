from uuid import UUID
from decimal import Decimal
from datetime import datetime, time as time_cls
from fastapi import HTTPException

from app.services import billing_service


# Offer CRUD 

async def create_offer(db, schema: str, outlet_id: UUID, data: dict, created_by: UUID) -> dict:
    if data.get("category_id"):
        cat = await db.fetchrow(
            f'SELECT id FROM "{schema}".menu_categories WHERE id = $1 AND outlet_id = $2',
            data["category_id"], outlet_id
        )
        if not cat:
            raise HTTPException(404, "Category not found")

    if data.get("item_id"):
        item = await db.fetchrow(
            f'SELECT id FROM "{schema}".menu_items WHERE id = $1 AND outlet_id = $2',
            data["item_id"], outlet_id
        )
        if not item:
            raise HTTPException(404, "Menu item not found")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".menu_offers
            (outlet_id, name, offer_type, discount_value, start_time, end_time,
             days_of_week, applies_to, category_id, item_id, created_by)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        RETURNING *
        """,
        outlet_id,
        data["name"],
        data["offer_type"],
        data["discount_value"],
        data.get("start_time"),
        data.get("end_time"),
        data.get("days_of_week"),
        data.get("applies_to", "all"),
        data.get("category_id"),
        data.get("item_id"),
        created_by,
    )
    return dict(row)


async def list_offers(db, schema: str, outlet_id: UUID, active_only: bool = False) -> list[dict]:
    if active_only:
        rows = await db.fetch(
            f"""SELECT * FROM "{schema}".menu_offers
                WHERE outlet_id = $1 AND is_active = TRUE
                ORDER BY name""",
            outlet_id
        )
    else:
        rows = await db.fetch(
            f"""SELECT * FROM "{schema}".menu_offers
                WHERE outlet_id = $1
                ORDER BY name""",
            outlet_id
        )
    return [dict(r) for r in rows]


async def get_offer(db, schema: str, outlet_id: UUID, offer_id: UUID) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".menu_offers WHERE id = $1 AND outlet_id = $2',
        offer_id, outlet_id
    )
    if not row:
        raise HTTPException(404, "Offer not found")
    return dict(row)


async def update_offer(db, schema: str, outlet_id: UUID, offer_id: UUID, data: dict) -> dict:
    await get_offer(db, schema, outlet_id, offer_id)

    fields = []
    values = []
    idx = 1
    for field in ["name", "discount_value", "start_time", "end_time",
                  "days_of_week", "is_active"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1

    if not fields:
        return await get_offer(db, schema, outlet_id, offer_id)

    values.append(offer_id)
    await db.execute(
        f"""UPDATE "{schema}".menu_offers SET {', '.join(fields)}, updated_at = NOW()
            WHERE id = ${idx}""",
        *values
    )
    return await get_offer(db, schema, outlet_id, offer_id)


async def delete_offer(db, schema: str, outlet_id: UUID, offer_id: UUID) -> dict:
    await get_offer(db, schema, outlet_id, offer_id)
    in_use = await db.fetchrow(
        f'SELECT id FROM "{schema}".bill_offers WHERE offer_id = $1 LIMIT 1',
        offer_id
    )
    if in_use:
        raise HTTPException(400, "Cannot delete an offer that has been applied to bills")
    await db.execute(
        f'DELETE FROM "{schema}".menu_offers WHERE id = $1',
        offer_id
    )
    return {"detail": "Offer deleted"}


# Eligibility 

def _is_time_eligible(offer: dict, now: datetime) -> bool:
    if offer["start_time"] and offer["end_time"]:
        current_time = now.time()
        if not (offer["start_time"] <= current_time <= offer["end_time"]):
            return False
    if offer["days_of_week"]:
        # Python weekday(): Mon=0..Sun=6 -> convert to Sun=0..Sat=6 convention used in DB
        py_weekday = now.weekday()
        sun_based = (py_weekday + 1) % 7
        if sun_based not in offer["days_of_week"]:
            return False
    return True


async def list_eligible_offers(db, schema: str, outlet_id: UUID, now: datetime = None) -> list[dict]:
    if now is None:
        now = datetime.now()
    rows = await db.fetch(
        f"""SELECT * FROM "{schema}".menu_offers
            WHERE outlet_id = $1 AND is_active = TRUE
            ORDER BY name""",
        outlet_id
    )
    eligible = []
    for r in rows:
        offer = dict(r)
        if _is_time_eligible(offer, now):
            eligible.append(offer)
    return eligible


# Bill application 

async def _validate_offer_against_order(db, schema: str, offer: dict, order_id: UUID):
    """Raises 400 if the offer's item/category requirement isn't met by the order."""
    if offer["applies_to"] == "all":
        return

    items = await db.fetch(
        f"""
        SELECT oi.menu_item_id, mi.category_id
        FROM "{schema}".order_items oi
        JOIN "{schema}".menu_items mi ON mi.id = oi.menu_item_id
        WHERE oi.order_id = $1 AND oi.status != 'cancelled'
        """,
        order_id
    )

    if offer["applies_to"] == "item":
        if not any(i["menu_item_id"] == offer["item_id"] for i in items):
            raise HTTPException(
                400,
                f"Offer '{offer['name']}' requires a specific item not present in this order"
            )
    elif offer["applies_to"] == "category":
        if not any(i["category_id"] == offer["category_id"] for i in items):
            raise HTTPException(
                400,
                f"Offer '{offer['name']}' requires an item from a category not present in this order"
            )


def _compute_offer_discount(offer: dict, subtotal: Decimal, scoped_total: Decimal) -> Decimal:
    """
    scoped_total = subtotal of just the matching items/category for item/category-scoped
    offers, or the full subtotal for 'all'-scoped offers.
    """
    value = Decimal(str(offer["discount_value"]))
    if offer["offer_type"] in ("percentage", "happy_hour", "combo"):
        # happy_hour/combo here are treated as percentage-style unless a flat semantic
        # is desired; discount_value drives the calc consistently as a percentage
        # when offer_type isn't explicitly 'flat'.
        return (scoped_total * value / 100).quantize(Decimal("0.01"))
    elif offer["offer_type"] in ("flat", "item_specific"):
        return min(value, scoped_total).quantize(Decimal("0.01"))
    return Decimal("0.00")


async def _scoped_subtotal(db, schema: str, offer: dict, order_id: UUID, full_subtotal: Decimal) -> Decimal:
    if offer["applies_to"] == "all":
        return full_subtotal

    if offer["applies_to"] == "item":
        total = await db.fetchval(
            f"""
            SELECT COALESCE(SUM(oi.unit_price * oi.quantity), 0)
            FROM "{schema}".order_items oi
            WHERE oi.order_id = $1 AND oi.menu_item_id = $2 AND oi.status != 'cancelled'
            """,
            order_id, offer["item_id"]
        )
        return Decimal(str(total))

    if offer["applies_to"] == "category":
        total = await db.fetchval(
            f"""
            SELECT COALESCE(SUM(oi.unit_price * oi.quantity), 0)
            FROM "{schema}".order_items oi
            JOIN "{schema}".menu_items mi ON mi.id = oi.menu_item_id
            WHERE oi.order_id = $1 AND mi.category_id = $2 AND oi.status != 'cancelled'
            """,
            order_id, offer["category_id"]
        )
        return Decimal(str(total))

    return full_subtotal


async def apply_offer(
    db, schema: str, outlet_id: UUID, bill_id: UUID,
    offer_id: UUID, applied_by: UUID, now: datetime = None
) -> dict:
    bill = await db.fetchrow(
        f"""SELECT id, status, order_id, subtotal
            FROM "{schema}".bills WHERE id = $1 AND outlet_id = $2""",
        bill_id, outlet_id
    )
    if not bill:
        raise HTTPException(404, "Bill not found")
    if bill["status"] != "open":
        raise HTTPException(400, "Can only apply offers to open bills")

    offer = await get_offer(db, schema, outlet_id, offer_id)
    if not offer["is_active"]:
        raise HTTPException(400, "This offer is not currently active")

    if now is None:
        now = datetime.now()
    if not _is_time_eligible(offer, now):
        raise HTTPException(400, f"Offer '{offer['name']}' is not valid at this time")

    already_applied = await db.fetchrow(
        f'SELECT id FROM "{schema}".bill_offers WHERE bill_id = $1 AND offer_id = $2',
        bill_id, offer_id
    )
    if already_applied:
        raise HTTPException(400, "This offer has already been applied to this bill")

    if not bill["order_id"]:
        raise HTTPException(400, "This bill has no linked order to validate the offer against")

    await _validate_offer_against_order(db, schema, offer, bill["order_id"])

    full_subtotal = Decimal(str(bill["subtotal"]))
    scoped_total = await _scoped_subtotal(db, schema, offer, bill["order_id"], full_subtotal)
    discount_amt = _compute_offer_discount(offer, full_subtotal, scoped_total)

    await db.execute(
        f"""
        INSERT INTO "{schema}".bill_offers (bill_id, offer_id, discount_amt, applied_by)
        VALUES ($1, $2, $3, $4)
        """,
        bill_id, offer_id, discount_amt, applied_by
    )

    await _recalculate_bill_totals(db, schema, bill_id)

    return await billing_service.get_bill(db, schema, outlet_id, bill_id)


async def remove_offer(db, schema: str, outlet_id: UUID, bill_id: UUID, offer_id: UUID) -> dict:
    bill = await db.fetchrow(
        f"""SELECT id, status FROM "{schema}".bills WHERE id = $1 AND outlet_id = $2""",
        bill_id, outlet_id
    )
    if not bill:
        raise HTTPException(404, "Bill not found")
    if bill["status"] != "open":
        raise HTTPException(400, "Can only remove offers from open bills")

    result = await db.execute(
        f'DELETE FROM "{schema}".bill_offers WHERE bill_id = $1 AND offer_id = $2',
        bill_id, offer_id
    )
    if result == "DELETE 0":
        raise HTTPException(404, "This offer is not applied to this bill")

    await _recalculate_bill_totals(db, schema, bill_id)

    return await billing_service.get_bill(db, schema, outlet_id, bill_id)


async def list_bill_offers(db, schema: str, bill_id: UUID) -> list[dict]:
    rows = await db.fetch(
        f"""
        SELECT bo.*, mo.name AS offer_name, mo.offer_type
        FROM "{schema}".bill_offers bo
        JOIN "{schema}".menu_offers mo ON mo.id = bo.offer_id
        WHERE bo.bill_id = $1
        ORDER BY bo.created_at
        """,
        bill_id
    )
    return [dict(r) for r in rows]


async def _recalculate_bill_totals(db, schema: str, bill_id: UUID):
    """
    Combined discount = manual bill_discounts + applied bill_offers.
    Recomputes bills.discount_amt and bills.total_amount consistently,
    matching the formula used in billing_service.apply_discount.
    """
    bill = await db.fetchrow(
        f"""SELECT subtotal, service_charge_amt, vat_amt
            FROM "{schema}".bills WHERE id = $1""",
        bill_id
    )

    manual_discount = await db.fetchval(
        f"""SELECT COALESCE(SUM(discount_amt), 0)
            FROM "{schema}".bill_discounts WHERE bill_id = $1""",
        bill_id
    )
    offer_discount = await db.fetchval(
        f"""SELECT COALESCE(SUM(discount_amt), 0)
            FROM "{schema}".bill_offers WHERE bill_id = $1""",
        bill_id
    )

    total_discount = Decimal(str(manual_discount)) + Decimal(str(offer_discount))
    subtotal = Decimal(str(bill["subtotal"]))
    sc_amt = Decimal(str(bill["service_charge_amt"]))
    vat_amt = Decimal(str(bill["vat_amt"]))

    new_total = subtotal + sc_amt + vat_amt - total_discount

    await db.execute(
        f"""
        UPDATE "{schema}".bills
        SET discount_amt = $1, total_amount = $2, updated_at = NOW()
        WHERE id = $3
        """,
        total_discount, new_total, bill_id
    )