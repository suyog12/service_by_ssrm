from uuid import UUID
from decimal import Decimal
from datetime import date
from fastapi import HTTPException


# Expense Categories 

async def create_category(db, schema: str, data: dict) -> dict:
    name = data["name"].strip()
    if not name:
        raise HTTPException(400, "Category name cannot be empty")

    existing = await db.fetchrow(
        f'SELECT id FROM "{schema}".expense_categories WHERE name = $1', name
    )
    if existing:
        raise HTTPException(400, f"Category '{name}' already exists")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".expense_categories (name, description, is_petty)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        name, data.get("description"), data.get("is_petty", False)
    )
    return dict(row)


async def list_categories(db, schema: str) -> list[dict]:
    rows = await db.fetch(
        f'SELECT * FROM "{schema}".expense_categories ORDER BY name'
    )
    return [dict(r) for r in rows]


async def get_category(db, schema: str, category_id: UUID) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".expense_categories WHERE id = $1',
        category_id
    )
    if not row:
        raise HTTPException(404, "Expense category not found")
    return dict(row)


async def update_category(
    db, schema: str, category_id: UUID, data: dict
) -> dict:
    await get_category(db, schema, category_id)

    fields = []
    values = []
    idx = 1
    for field in ["name", "description", "is_petty"]:
        if field in data and data[field] is not None:
            val = data[field].strip() if field == "name" else data[field]
            if field == "name" and not val:
                raise HTTPException(400, "Category name cannot be empty")
            fields.append(f"{field} = ${idx}")
            values.append(val)
            idx += 1

    if not fields:
        return await get_category(db, schema, category_id)

    values.append(category_id)
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".expense_categories
        SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING *
        """,
        *values
    )
    return dict(row)


async def delete_category(db, schema: str, category_id: UUID) -> None:
    await get_category(db, schema, category_id)

    in_use = await db.fetchval(
        f'SELECT COUNT(*) FROM "{schema}".expense_logs WHERE category_id = $1',
        category_id
    )
    if in_use:
        raise HTTPException(
            400, "Cannot delete category with existing expense logs"
        )

    await db.execute(
        f'DELETE FROM "{schema}".expense_categories WHERE id = $1',
        category_id
    )


# Expense Logs 

async def create_expense(
    db, schema: str, data: dict, logged_by: UUID
) -> dict:
    category = await db.fetchrow(
        f'SELECT id FROM "{schema}".expense_categories WHERE id = $1',
        data["category_id"]
    )
    if not category:
        raise HTTPException(404, "Expense category not found")

    if data.get("supplier_id"):
        supplier = await db.fetchrow(
            f'SELECT id FROM "{schema}".suppliers WHERE id = $1',
            data["supplier_id"]
        )
        if not supplier:
            raise HTTPException(404, "Supplier not found")

    if data.get("po_id"):
        po = await db.fetchrow(
            f'SELECT id FROM "{schema}".purchase_orders WHERE id = $1',
            data["po_id"]
        )
        if not po:
            raise HTTPException(404, "Purchase order not found")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".expense_logs
            (outlet_id, category_id, amount, description, receipt_url,
             logged_by, expense_date, is_petty, supplier_id, po_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING *
        """,
        data.get("outlet_id"),
        data["category_id"],
        data["amount"],
        data["description"].strip(),
        data.get("receipt_url"),
        logged_by,
        data["expense_date"],
        data.get("is_petty", False),
        data.get("supplier_id"),
        data.get("po_id"),
    )
    return dict(row)


async def list_expenses(
    db, schema: str,
    outlet_id: UUID = None,
    category_id: UUID = None,
    is_petty: bool = None,
    date_from: date = None,
    date_to: date = None,
) -> list[dict]:
    conditions = []
    values = []
    idx = 1

    if outlet_id:
        conditions.append(f"el.outlet_id = ${idx}")
        values.append(outlet_id)
        idx += 1
    if category_id:
        conditions.append(f"el.category_id = ${idx}")
        values.append(category_id)
        idx += 1
    if is_petty is not None:
        conditions.append(f"el.is_petty = ${idx}")
        values.append(is_petty)
        idx += 1
    if date_from:
        conditions.append(f"el.expense_date >= ${idx}")
        values.append(date_from)
        idx += 1
    if date_to:
        conditions.append(f"el.expense_date <= ${idx}")
        values.append(date_to)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = await db.fetch(
        f"""
        SELECT el.*, ec.name AS category_name
        FROM "{schema}".expense_logs el
        JOIN "{schema}".expense_categories ec ON ec.id = el.category_id
        {where}
        ORDER BY el.expense_date DESC, el.created_at DESC
        """,
        *values
    )
    return [dict(r) for r in rows]


async def get_expense(db, schema: str, expense_id: UUID) -> dict:
    row = await db.fetchrow(
        f"""
        SELECT el.*, ec.name AS category_name
        FROM "{schema}".expense_logs el
        JOIN "{schema}".expense_categories ec ON ec.id = el.category_id
        WHERE el.id = $1
        """,
        expense_id
    )
    if not row:
        raise HTTPException(404, "Expense not found")
    return dict(row)


async def delete_expense(db, schema: str, expense_id: UUID) -> None:
    await get_expense(db, schema, expense_id)
    await db.execute(
        f'DELETE FROM "{schema}".expense_logs WHERE id = $1', expense_id
    )


# Cash Register 

async def cash_register_action(
    db, schema: str, outlet_id: UUID, data: dict, user_id: UUID
) -> dict:
    action = data["action"]

    if action == "open":
        existing_open = await db.fetchrow(
            f"""
            SELECT id FROM "{schema}".cash_register
            WHERE outlet_id = $1 AND action = 'open'
            AND created_at::date = CURRENT_DATE
            """,
            outlet_id
        )
        if existing_open:
            raise HTTPException(400, "Cash register already opened for today")

    if action == "close":
        opened = await db.fetchrow(
            f"""
            SELECT cash_amount FROM "{schema}".cash_register
            WHERE outlet_id = $1 AND action = 'open'
            AND created_at::date = CURRENT_DATE
            ORDER BY created_at DESC LIMIT 1
            """,
            outlet_id
        )
        if not opened:
            raise HTTPException(400, "No open cash register found for today")

        total_cash_payments = await db.fetchval(
            f"""
            SELECT COALESCE(SUM(p.amount), 0)
            FROM "{schema}".payments p
            JOIN "{schema}".bills b ON b.id = p.bill_id
            WHERE b.outlet_id = $1
              AND p.method = 'cash'
              AND p.status = 'completed'
              AND p.created_at::date = CURRENT_DATE
            """,
            outlet_id
        )

        opening_amount = Decimal(str(opened["cash_amount"]))
        expected = opening_amount + Decimal(str(total_cash_payments))
        closing = Decimal(str(data["cash_amount"]))
        discrepancy = closing - expected

        row = await db.fetchrow(
            f"""
            INSERT INTO "{schema}".cash_register
                (outlet_id, user_id, shift_id, action, cash_amount,
                 expected_amount, discrepancy, notes)
            VALUES ($1, $2, $3, 'close', $4, $5, $6, $7)
            RETURNING *
            """,
            outlet_id, user_id, data.get("shift_id"),
            closing, expected, discrepancy, data.get("notes")
        )
        return dict(row)

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".cash_register
            (outlet_id, user_id, shift_id, action, cash_amount, notes)
        VALUES ($1, $2, $3, 'open', $4, $5)
        RETURNING *
        """,
        outlet_id, user_id, data.get("shift_id"),
        data["cash_amount"], data.get("notes")
    )
    return dict(row)


async def list_cash_register(
    db, schema: str, outlet_id: UUID, date_filter: date = None
) -> list[dict]:
    if date_filter:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".cash_register
            WHERE outlet_id = $1 AND (created_at AT TIME ZONE 'Asia/Kathmandu')::date = $2
            ORDER BY created_at DESC
            """,
            outlet_id, date_filter
        )
    else:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".cash_register
            WHERE outlet_id = $1
            ORDER BY created_at DESC
            LIMIT 30
            """,
            outlet_id
        )
    return [dict(r) for r in rows]