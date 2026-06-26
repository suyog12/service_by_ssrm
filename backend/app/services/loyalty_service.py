from uuid import UUID
from decimal import Decimal
from fastapi import HTTPException


# Settings

async def get_settings(db, schema: str) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".loyalty_settings LIMIT 1'
    )
    if not row:
        row = await db.fetchrow(
            f"""
            INSERT INTO "{schema}".loyalty_settings DEFAULT VALUES
            RETURNING *
            """
        )
    return dict(row)


async def update_settings(db, schema: str, data: dict) -> dict:
    settings = await get_settings(db, schema)

    fields = []
    values = []
    idx = 1
    for field in ["is_enabled", "points_per_amount", "amount_per_point",
                  "redemption_rate", "points_expiry_days", "min_redemption_pts"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1

    if not fields:
        return settings

    values.append(settings["id"])
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".loyalty_settings
        SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        RETURNING *
        """,
        *values
    )
    return dict(row)


# Enrollment

async def enroll_customer(db, schema: str, customer_id: UUID) -> dict:
    customer = await db.fetchrow(
        f'SELECT id, full_name FROM "{schema}".customers WHERE id = $1',
        customer_id
    )
    if not customer:
        raise HTTPException(404, "Customer not found")

    existing = await db.fetchrow(
        f'SELECT id FROM "{schema}".loyalty_accounts WHERE customer_id = $1',
        customer_id
    )
    if existing:
        raise HTTPException(400, "Customer is already enrolled in the loyalty program")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".loyalty_accounts
            (customer_id, points_balance, lifetime_points, tier)
        VALUES ($1, 0, 0, 'standard')
        RETURNING *
        """,
        customer_id
    )
    return dict(row)


async def get_account(db, schema: str, customer_id: UUID) -> dict:
    row = await db.fetchrow(
        f"""
        SELECT la.*, c.full_name, c.phone, c.email
        FROM "{schema}".loyalty_accounts la
        JOIN "{schema}".customers c ON c.id = la.customer_id
        WHERE la.customer_id = $1
        """,
        customer_id
    )
    if not row:
        raise HTTPException(404, "Customer does not have a loyalty account")
    return dict(row)


async def get_account_by_id(db, schema: str, account_id: UUID) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".loyalty_accounts WHERE id = $1',
        account_id
    )
    if not row:
        raise HTTPException(404, "Loyalty account not found")
    return dict(row)


async def list_transactions(db, schema: str, customer_id: UUID) -> list[dict]:
    account = await get_account(db, schema, customer_id)
    rows = await db.fetch(
        f"""
        SELECT * FROM "{schema}".loyalty_transactions
        WHERE loyalty_account_id = $1
        ORDER BY created_at DESC
        """,
        account["id"]
    )
    return [dict(r) for r in rows]


# Earn — called from billing_service after payment

async def award_points_for_bill(db, schema: str, bill_id: UUID):
    """
    Called automatically after a bill is marked 'paid'.
    No-ops silently if loyalty is disabled or customer has no account.
    """
    settings = await get_settings(db, schema)
    if not settings["is_enabled"]:
        return

    bill = await db.fetchrow(
        f'SELECT customer_id, total_amount, points_redeemed FROM "{schema}".bills WHERE id = $1',
        bill_id
    )
    if not bill or not bill["customer_id"]:
        return

    account = await db.fetchrow(
        f'SELECT id, points_balance, lifetime_points FROM "{schema}".loyalty_accounts WHERE customer_id = $1',
        bill["customer_id"]
    )
    if not account:
        return

    # Earn points on the amount actually paid (after any redemption deduction)
    billable_amount = Decimal(str(bill["total_amount"]))
    points_rate = Decimal(str(settings["points_per_amount"]))
    earned = int(billable_amount * points_rate)

    if earned <= 0:
        return

    new_balance = account["points_balance"] + earned
    new_lifetime = account["lifetime_points"] + earned

    await db.execute(
        f"""
        UPDATE "{schema}".loyalty_accounts
        SET points_balance = $1, lifetime_points = $2, updated_at = NOW()
        WHERE id = $3
        """,
        new_balance, new_lifetime, account["id"]
    )

    await db.execute(
        f"""
        INSERT INTO "{schema}".loyalty_transactions
            (loyalty_account_id, transaction_type, points, reference_id, notes)
        VALUES ($1, 'earn', $2, $3, $4)
        """,
        account["id"], earned, bill_id, f"Points earned from bill payment"
    )


# Redeem — called at billing before payment

async def redeem_points_on_bill(
    db, schema: str, outlet_id: UUID,
    bill_id: UUID, points_to_redeem: int
) -> dict:
    # Fetch bill first — always 404 before any other error
    bill = await db.fetchrow(
        f"""
        SELECT id, status, customer_id, total_amount, subtotal,
               service_charge_amt, vat_amt, discount_amt
        FROM "{schema}".bills
        WHERE id = $1 AND outlet_id = $2
        """,
        bill_id, outlet_id
    )
    if not bill:
        raise HTTPException(404, "Bill not found")

    settings = await get_settings(db, schema)
    if not settings["is_enabled"]:
        raise HTTPException(400, "Loyalty program is not enabled")

    min_pts = settings["min_redemption_pts"]
    if points_to_redeem < min_pts:
        raise HTTPException(
            400,
            f"Minimum redemption is {min_pts} points"
        )
    if bill["status"] != "open":
        raise HTTPException(400, "Can only redeem points on open bills")
    if not bill["customer_id"]:
        raise HTTPException(400, "This bill has no linked customer to redeem points for")

    account = await db.fetchrow(
        f"""
        SELECT id, points_balance
        FROM "{schema}".loyalty_accounts
        WHERE customer_id = $1
        """,
        bill["customer_id"]
    )
    if not account:
        raise HTTPException(400, "Customer does not have a loyalty account")

    if account["points_balance"] < points_to_redeem:
        raise HTTPException(
            400,
            f"Insufficient points. Available: {account['points_balance']}, "
            f"Requested: {points_to_redeem}"
        )

    amount_per_point = Decimal(str(settings["amount_per_point"]))
    points_value = (Decimal(points_to_redeem) * amount_per_point).quantize(Decimal("0.01"))

    # Cap at bill total to avoid negative totals
    subtotal = Decimal(str(bill["subtotal"]))
    sc_amt = Decimal(str(bill["service_charge_amt"]))
    vat_amt = Decimal(str(bill["vat_amt"]))
    current_discount = Decimal(str(bill["discount_amt"]))
    max_redeemable = subtotal + sc_amt + vat_amt - current_discount
    if points_value > max_redeemable:
        points_value = max_redeemable
        points_to_redeem = int(points_value / amount_per_point)

    # Deduct points immediately
    new_balance = account["points_balance"] - points_to_redeem
    await db.execute(
        f"""
        UPDATE "{schema}".loyalty_accounts
        SET points_balance = $1, updated_at = NOW()
        WHERE id = $2
        """,
        new_balance, account["id"]
    )

    await db.execute(
        f"""
        INSERT INTO "{schema}".loyalty_transactions
            (loyalty_account_id, transaction_type, points, reference_id, notes)
        VALUES ($1, 'redeem', $2, $3, $4)
        """,
        account["id"], -points_to_redeem, bill_id,
        f"Points redeemed against bill"
    )

    # Write to bill and recalculate total
    new_total = subtotal + sc_amt + vat_amt - current_discount - points_value
    await db.execute(
        f"""
        UPDATE "{schema}".bills
        SET points_redeemed = $1, points_value = $2,
            total_amount = $3, updated_at = NOW()
        WHERE id = $4
        """,
        points_to_redeem, points_value, new_total, bill_id
    )

    # Return full bill using billing_service pattern
    from app.services import billing_service
    return await billing_service.get_bill(db, schema, outlet_id, bill_id)


async def void_redemption(db, schema: str, bill_id: UUID):
    """
    Called when a bill is voided — returns redeemed points to the customer.
    No-op if no points were redeemed.
    """
    bill = await db.fetchrow(
        f'SELECT customer_id, points_redeemed FROM "{schema}".bills WHERE id = $1',
        bill_id
    )
    if not bill or not bill["customer_id"] or not bill["points_redeemed"]:
        return

    points_to_return = bill["points_redeemed"]
    if points_to_return <= 0:
        return

    account = await db.fetchrow(
        f'SELECT id, points_balance FROM "{schema}".loyalty_accounts WHERE customer_id = $1',
        bill["customer_id"]
    )
    if not account:
        return

    new_balance = account["points_balance"] + points_to_return
    await db.execute(
        f"""
        UPDATE "{schema}".loyalty_accounts
        SET points_balance = $1, updated_at = NOW()
        WHERE id = $2
        """,
        new_balance, account["id"]
    )

    await db.execute(
        f"""
        INSERT INTO "{schema}".loyalty_transactions
            (loyalty_account_id, transaction_type, points, reference_id, notes)
        VALUES ($1, 'adjust', $2, $3, $4)
        """,
        account["id"], points_to_return, bill_id,
        "Points returned due to bill void"
    )