from uuid import UUID
from fastapi import HTTPException
from decimal import Decimal
import secrets
import string
from datetime import datetime
from collections import defaultdict
from app.services import hotel_service
from app.utils.nepali_date import to_bs, add_bs_fields
from app.services.offer_service import _recalculate_bill_totals


def _generate_bill_number() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(6))
    return f"BILL-{suffix}"


async def _track_customer_visit(db, schema: str, bill_id: UUID):
    bill = await db.fetchrow(
        f'SELECT customer_id, total_amount FROM "{schema}".bills WHERE id = $1',
        bill_id
    )
    if bill and bill["customer_id"]:
        await db.execute(
            f"""
            UPDATE "{schema}".customers
            SET total_visits = total_visits + 1,
                total_spent = total_spent + $1,
                updated_at = NOW()
            WHERE id = $2
            """,
            bill["total_amount"], bill["customer_id"]
        )


# Billing Settings

async def get_or_create_billing_settings(
    db, schema: str, outlet_id: UUID
) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".billing_settings WHERE outlet_id = $1',
        outlet_id
    )
    if not row:
        row = await db.fetchrow(
            f"""
            INSERT INTO "{schema}".billing_settings (outlet_id)
            VALUES ($1)
            RETURNING *
            """,
            outlet_id
        )
    return dict(row)


async def update_billing_settings(
    db, schema: str, outlet_id: UUID, data: dict
) -> dict:
    settings = await get_or_create_billing_settings(db, schema, outlet_id)
    settings_id = settings["id"]

    fields = []
    values = []
    idx = 1
    for field in ["vat_mode", "vat_pct", "service_charge_mode",
                  "service_charge_pct", "qr_type", "qr_image_url",
                  "fonepay_merchant_id"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1

    if not fields:
        return settings

    values.append(settings_id)
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".billing_settings
        SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        RETURNING *
        """,
        *values
    )
    return dict(row)


# Bill Generation

async def generate_bill(
    db, schema: str, outlet_id: UUID, data: dict, generated_by: UUID
) -> dict:
    order_id = data["order_id"]

    order = await db.fetchrow(
        f"""
        SELECT id, status, order_number
        FROM "{schema}".orders
        WHERE id = $1 AND outlet_id = $2
        """,
        order_id, outlet_id
    )
    if not order:
        raise HTTPException(404, "Order not found")
    if order["status"] in ("billed", "cancelled"):
        raise HTTPException(400, "Order is already billed or cancelled")

    existing = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".bills
        WHERE order_id = $1 AND status NOT IN ('voided')
        """,
        order_id
    )
    if existing:
        raise HTTPException(400, "An active bill already exists for this order")

    settings = await get_or_create_billing_settings(db, schema, outlet_id)

    tenant = await db.fetchrow(
        'SELECT vat_registered, vat_pct FROM core.tenants WHERE schema_name = $1',
        schema
    )
    tenant_vat_registered = tenant["vat_registered"] if tenant else False

    items = await db.fetch(
        f"""
        SELECT oi.id, oi.quantity, oi.unit_price,
               mi.name AS item_name, mi.tax_rate, mi.category_id
        FROM "{schema}".order_items oi
        JOIN "{schema}".menu_items mi ON mi.id = oi.menu_item_id
        WHERE oi.order_id = $1 AND oi.status != 'cancelled'
        """,
        order_id
    )
    if not items:
        raise HTTPException(400, "Order has no items to bill")

    subtotal = sum(
        Decimal(str(item["unit_price"])) * item["quantity"]
        for item in items
    )

    vat_pct = Decimal(str(settings["vat_pct"]))
    vat_mode = settings["vat_mode"]
    if tenant_vat_registered:
        if vat_mode == "exclusive":
            vat_amt = (subtotal * vat_pct / 100).quantize(Decimal("0.01"))
        else:
            vat_amt = (subtotal * vat_pct / (100 + vat_pct)).quantize(Decimal("0.01"))
    else:
        vat_amt = Decimal("0.00")
        vat_pct = Decimal("0.00")

    sc_pct = Decimal(str(settings["service_charge_pct"]))
    sc_mode = settings["service_charge_mode"]
    if sc_mode == "exclusive":
        sc_amt = (subtotal * sc_pct / 100).quantize(Decimal("0.01"))
    else:
        sc_amt = (subtotal * sc_pct / (100 + sc_pct)).quantize(Decimal("0.01"))

    total = subtotal
    if vat_mode == "exclusive" and tenant_vat_registered:
        total += vat_amt
    if sc_mode == "exclusive":
        total += sc_amt

    for _ in range(10):
        bill_number = _generate_bill_number()
        existing_num = await db.fetchrow(
            f'SELECT id FROM "{schema}".bills WHERE bill_number = $1',
            bill_number
        )
        if not existing_num:
            break

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".bills
            (outlet_id, bill_number, order_id, customer_id, credit_account_id,
             is_corporate, corporate_name, corporate_pan,
             subtotal, service_charge_pct, service_charge_amt,
             vat_pct, vat_amt, total_amount, generated_by)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
        RETURNING id, bill_number, order_id, customer_id, credit_account_id,
                  is_corporate, corporate_name, corporate_pan,
                  subtotal, service_charge_pct, service_charge_amt,
                  vat_pct, vat_amt, discount_amt, total_amount,
                  status, generated_by, created_at
        """,
        outlet_id,
        bill_number,
        order_id,
        data.get("customer_id"),
        data.get("credit_account_id"),
        data.get("is_corporate", False),
        data.get("corporate_name"),
        data.get("corporate_pan"),
        subtotal,
        sc_pct,
        sc_amt,
        vat_pct,
        vat_amt,
        total,
        generated_by,
    )

    result = dict(row)
    result["items"] = await _get_bill_line_items(db, schema, order_id)
    result["qr_type"] = settings["qr_type"]
    result["qr_image_url"] = settings["qr_image_url"]
    result["created_at_bs"] = to_bs(result["created_at"])
    return result


async def get_bill(
    db, schema: str, outlet_id: UUID, bill_id: UUID
) -> dict:
    row = await db.fetchrow(
        f"""
        SELECT id, bill_number, order_id, customer_id, credit_account_id,
               is_corporate, corporate_name, corporate_pan,
               subtotal, service_charge_pct, service_charge_amt,
               vat_pct, vat_amt, discount_amt, total_amount,
               status, generated_by, created_at
        FROM "{schema}".bills
        WHERE id = $1 AND outlet_id = $2
        """,
        bill_id, outlet_id
    )
    if not row:
        raise HTTPException(404, "Bill not found")

    result = dict(row)
    if result["order_id"]:
        result["items"] = await _get_bill_line_items(
            db, schema, result["order_id"]
        )
    else:
        result["items"] = []

    settings = await get_or_create_billing_settings(db, schema, outlet_id)
    result["qr_type"] = settings["qr_type"]
    result["qr_image_url"] = settings["qr_image_url"]
    result["created_at_bs"] = to_bs(result["created_at"])
    return result


async def list_bills(
    db, schema: str, outlet_id: UUID, status: str = None
) -> list[dict]:
    if status:
        rows = await db.fetch(
            f"""
            SELECT id, bill_number, order_id, customer_id, credit_account_id,
                   is_corporate, corporate_name, subtotal,
                   service_charge_amt, vat_amt, discount_amt, total_amount,
                   status, generated_by, created_at
            FROM "{schema}".bills
            WHERE outlet_id = $1 AND status = $2
            ORDER BY created_at DESC
            """,
            outlet_id, status
        )
    else:
        rows = await db.fetch(
            f"""
            SELECT id, bill_number, order_id, customer_id, credit_account_id,
                   is_corporate, corporate_name, subtotal,
                   service_charge_amt, vat_amt, discount_amt, total_amount,
                   status, generated_by, created_at
            FROM "{schema}".bills
            WHERE outlet_id = $1
            ORDER BY created_at DESC
            """,
            outlet_id
        )
    return [add_bs_fields(dict(r), ["created_at"]) for r in rows]


async def apply_discount(
    db, schema: str, outlet_id: UUID, bill_id: UUID,
    data: dict, applied_by: UUID
) -> dict:
    bill = await db.fetchrow(
        f"""
        SELECT id, status, order_id, subtotal
        FROM "{schema}".bills
        WHERE id = $1 AND outlet_id = $2
        """,
        bill_id, outlet_id
    )
    if not bill:
        raise HTTPException(404, "Bill not found")
    if bill["status"] != "open":
        raise HTTPException(400, "Can only apply discounts to open bills")

    discount_pct = Decimal(str(data["discount_pct"]))
    discount_level = data["discount_level"]
    subtotal = Decimal(str(bill["subtotal"]))

    if discount_level == "bill":
        discount_amt = (subtotal * discount_pct / 100).quantize(Decimal("0.01"))
    elif discount_level == "category":
        category_id = data.get("category_id")
        if not category_id:
            raise HTTPException(400, "category_id required for category discount")
        cat_total = await db.fetchval(
            f"""
            SELECT COALESCE(SUM(oi.unit_price * oi.quantity), 0)
            FROM "{schema}".order_items oi
            JOIN "{schema}".menu_items mi ON mi.id = oi.menu_item_id
            WHERE oi.order_id = $1
              AND mi.category_id = $2
              AND oi.status != 'cancelled'
            """,
            bill["order_id"], category_id
        )
        discount_amt = (
            Decimal(str(cat_total)) * discount_pct / 100
        ).quantize(Decimal("0.01"))
    elif discount_level == "item":
        order_item_id = data.get("order_item_id")
        if not order_item_id:
            raise HTTPException(400, "order_item_id required for item discount")
        item = await db.fetchrow(
            f"""
            SELECT unit_price, quantity FROM "{schema}".order_items
            WHERE id = $1 AND order_id = $2
            """,
            order_item_id, bill["order_id"]
        )
        if not item:
            raise HTTPException(400, "Order item not found on this bill's order")
        item_total = Decimal(str(item["unit_price"])) * item["quantity"]
        discount_amt = (item_total * discount_pct / 100).quantize(Decimal("0.01"))
    else:
        raise HTTPException(400, "Invalid discount level")

    await db.execute(
        f"""
        INSERT INTO "{schema}".bill_discounts
            (bill_id, discount_level, category_id, order_item_id,
             discount_pct, discount_amt, applied_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        bill_id,
        discount_level,
        data.get("category_id"),
        data.get("order_item_id"),
        discount_pct,
        discount_amt,
        applied_by,
    )

    await _recalculate_bill_totals(db, schema, bill_id)
    return await get_bill(db, schema, outlet_id, bill_id)


async def process_payment(
    db, schema: str, outlet_id: UUID, bill_id: UUID,
    data: dict, processed_by: UUID
) -> dict:
    bill = await db.fetchrow(
        f"""
        SELECT id, status, total_amount, credit_account_id,
               reservation_id, bill_number
        FROM "{schema}".bills
        WHERE id = $1 AND outlet_id = $2
        """,
        bill_id, outlet_id
    )
    if not bill:
        raise HTTPException(404, "Bill not found")
    if bill["status"] in ("voided", "paid", "room_charge_posted"):
        raise HTTPException(400, f"Bill is already {bill['status']}")

    method = data["method"]
    amount = Decimal(str(data["amount"]))

    if method == "credit_account":
        credit_account_id = bill["credit_account_id"]
        if not credit_account_id:
            raise HTTPException(400, "No credit account linked to this bill")

        account = await db.fetchrow(
            f"""
            SELECT id, credit_limit, current_balance, is_active
            FROM "{schema}".credit_accounts WHERE id = $1
            """,
            credit_account_id
        )
        if not account:
            raise HTTPException(400, "Credit account not found")
        if not account["is_active"]:
            raise HTTPException(400, "Credit account is inactive")

        new_balance = (
            Decimal(str(account["current_balance"])) +
            Decimal(str(bill["total_amount"]))
        )
        if new_balance > Decimal(str(account["credit_limit"])):
            raise HTTPException(
                400,
                f"This would exceed the credit limit of Rs {account['credit_limit']}"
            )

        await db.execute(
            f"""
            UPDATE "{schema}".credit_accounts
            SET current_balance = $1, updated_at = NOW()
            WHERE id = $2
            """,
            new_balance, credit_account_id
        )

        await db.execute(
            f"""
            INSERT INTO "{schema}".credit_transactions
                (credit_account_id, transaction_type, amount, bill_id,
                 reference, processed_by)
            VALUES ($1, 'charge', $2, $3, $4, $5)
            """,
            credit_account_id,
            bill["total_amount"],
            bill_id,
            data.get("transaction_ref"),
            processed_by,
        )

        await db.execute(
            f"""
            UPDATE "{schema}".bills
            SET status = 'credit_posted', updated_at = NOW()
            WHERE id = $1
            """,
            bill_id
        )

    elif method == "room_charge":
        if not bill["reservation_id"]:
            raise HTTPException(
                400,
                "This bill is not linked to a hotel reservation"
            )

        await hotel_service.add_folio_charge(
            bill["reservation_id"],
            "restaurant",
            f"Bill {bill['bill_number']}",
            Decimal(str(bill["total_amount"])),
            schema,
            db,
            processed_by,
            reference_id=bill_id,
            reference_type="bill",
        )

        await db.execute(
            f"""
            UPDATE "{schema}".bills
            SET status = 'room_charge_posted', updated_at = NOW()
            WHERE id = $1
            """,
            bill_id
        )

        bill_row = await db.fetchrow(
            f'SELECT order_id FROM "{schema}".bills WHERE id = $1',
            bill_id
        )
        if bill_row and bill_row["order_id"]:
            order_row = await db.fetchrow(
                f'SELECT table_id FROM "{schema}".orders WHERE id = $1',
                bill_row["order_id"]
            )
            await db.execute(
                f"""
                UPDATE "{schema}".orders
                SET status = 'billed', updated_at = NOW()
                WHERE id = $1
                """,
                bill_row["order_id"]
            )
            if order_row and order_row["table_id"]:
                await db.execute(
                    f"""
                    UPDATE "{schema}".tables
                    SET status = 'available', updated_at = NOW()
                    WHERE id = $1
                    """,
                    order_row["table_id"]
                )

        await _track_customer_visit(db, schema, bill_id)
        from app.services.loyalty_service import award_points_for_bill
        await award_points_for_bill(db, schema, bill_id)

    else:
        await db.execute(
            f"""
            INSERT INTO "{schema}".payments
                (bill_id, method, amount, transaction_ref,
                 status, processed_by)
            VALUES ($1, $2, $3, $4, 'completed', $5)
            """,
            bill_id,
            method,
            amount,
            data.get("transaction_ref"),
            processed_by,
        )

        total_paid = await db.fetchval(
            f"""
            SELECT COALESCE(SUM(amount), 0)
            FROM "{schema}".payments
            WHERE bill_id = $1 AND status = 'completed'
            """,
            bill_id
        )

        bill_total = Decimal(str(bill["total_amount"]))
        total_paid_dec = Decimal(str(total_paid))

        if total_paid_dec >= bill_total:
            new_status = "paid"
        elif total_paid_dec > 0:
            new_status = "partial"
        else:
            new_status = bill["status"]

        await db.execute(
            f"""
            UPDATE "{schema}".bills
            SET status = $1, updated_at = NOW()
            WHERE id = $2
            """,
            new_status, bill_id
        )

        if new_status == "paid":
            bill_row = await db.fetchrow(
                f'SELECT order_id FROM "{schema}".bills WHERE id = $1',
                bill_id
            )
            if bill_row and bill_row["order_id"]:
                order_row = await db.fetchrow(
                    f'SELECT table_id FROM "{schema}".orders WHERE id = $1',
                    bill_row["order_id"]
                )
                await db.execute(
                    f"""
                    UPDATE "{schema}".orders
                    SET status = 'billed', updated_at = NOW()
                    WHERE id = $1
                    """,
                    bill_row["order_id"]
                )
                if order_row and order_row["table_id"]:
                    await db.execute(
                        f"""
                        UPDATE "{schema}".tables
                        SET status = 'available', updated_at = NOW()
                        WHERE id = $1
                        """,
                        order_row["table_id"]
                    )

            await _track_customer_visit(db, schema, bill_id)
            from app.services.loyalty_service import award_points_for_bill
            await award_points_for_bill(db, schema, bill_id)

    return await get_bill(db, schema, outlet_id, bill_id)


async def void_bill(
    db, schema: str, outlet_id: UUID, bill_id: UUID,
    reason: str, voided_by: UUID
) -> dict:
    bill = await db.fetchrow(
        f"""
        SELECT id, status FROM "{schema}".bills
        WHERE id = $1 AND outlet_id = $2
        """,
        bill_id, outlet_id
    )
    if not bill:
        raise HTTPException(404, "Bill not found")
    if bill["status"] == "voided":
        raise HTTPException(400, "Bill is already voided")
    if bill["status"] == "paid":
        raise HTTPException(400, "Cannot void a paid bill — use refund instead")

    await db.execute(
        f"""
        UPDATE "{schema}".bills
        SET status = 'voided', voided_by = $1,
            void_reason = $2, voided_at = NOW(), updated_at = NOW()
        WHERE id = $3
        """,
        voided_by, reason, bill_id
    )
    from app.services.loyalty_service import void_redemption
    await void_redemption(db, schema, bill_id)
    return await get_bill(db, schema, outlet_id, bill_id)


async def get_bill_html(
    db, schema: str, outlet_id: UUID, bill_id: UUID
) -> str:
    bill = await db.fetchrow(
        f"""
        SELECT b.id, b.bill_number, b.subtotal, b.service_charge_pct,
               b.service_charge_amt, b.vat_pct, b.vat_amt,
               b.discount_amt, b.total_amount, b.status,
               b.is_corporate, b.corporate_name, b.corporate_pan,
               b.created_at, o.order_number, o.order_type,
               t.table_number,
               tn.name        AS biz_name,
               tn.address     AS biz_address,
               tn.phone       AS biz_phone,
               tn.pan_number  AS biz_pan,
               tn.vat_registered,
               tn.vat_number
        FROM "{schema}".bills b
        LEFT JOIN "{schema}".orders o  ON o.id = b.order_id
        LEFT JOIN "{schema}".tables t  ON t.id = o.table_id
        LEFT JOIN core.tenants tn      ON tn.schema_name = $3
        WHERE b.id = $1 AND b.outlet_id = $2
        """,
        bill_id, outlet_id, schema
    )
    if not bill:
        raise HTTPException(404, "Bill not found")

    settings = await get_or_create_billing_settings(db, schema, outlet_id)

    items = []
    if bill["order_number"]:
        items = await db.fetch(
            f"""
            SELECT oi.quantity, oi.unit_price, mi.name AS item_name,
                   (oi.unit_price * oi.quantity) AS line_total
            FROM "{schema}".order_items oi
            JOIN "{schema}".menu_items mi ON mi.id = oi.menu_item_id
            WHERE oi.order_id = (
                SELECT order_id FROM "{schema}".bills WHERE id = $1
            )
            AND oi.status != 'cancelled'
            ORDER BY oi.created_at
            """,
            bill_id
        )

    items_html = ""
    for item in items:
        items_html += f"""
        <tr>
            <td>{item['item_name']}</td>
            <td class='right'>{item['quantity']}</td>
            <td class='right'>Rs {item['unit_price']:,.2f}</td>
            <td class='right'>Rs {item['line_total']:,.2f}</td>
        </tr>"""

    biz_name = bill["biz_name"] or "Restaurant"
    biz_address_line = (
        f"<div class='meta'>{bill['biz_address']}</div>"
        if bill["biz_address"] else ""
    )
    biz_phone_line = (
        f"<div class='meta'>Tel: {bill['biz_phone']}</div>"
        if bill["biz_phone"] else ""
    )

    if bill["vat_registered"] and bill["vat_number"]:
        biz_tax_line = (
            f"<div class='meta'>PAN: {bill['biz_pan']} &nbsp;|&nbsp; "
            f"VAT No: {bill['vat_number']}</div>"
        )
        invoice_type = "TAX INVOICE"
    elif bill["biz_pan"]:
        biz_tax_line = f"<div class='meta'>PAN: {bill['biz_pan']}</div>"
        invoice_type = "INVOICE"
    else:
        biz_tax_line = ""
        invoice_type = "INVOICE"

    if bill["table_number"]:
        table_info = f"Table: {bill['table_number']}"
    elif bill["order_type"]:
        table_info = bill["order_type"].replace("_", " ").title()
    else:
        table_info = ""

    bill_time = (
        bill["created_at"].strftime("%Y-%m-%d %H:%M")
        if bill["created_at"] else ""
    )

    corporate_html = ""
    if bill["is_corporate"] and bill["corporate_name"]:
        corporate_html = "<div class='section-label'>Bill To</div>"
        corporate_html += f"<div class='meta bold'>{bill['corporate_name']}</div>"
        if bill["corporate_pan"]:
            corporate_html += f"<div class='meta'>PAN: {bill['corporate_pan']}</div>"
        corporate_html = f"<div class='corporate-block'>{corporate_html}</div>"

    vat_line = ""
    if bill["vat_registered"] and bill["vat_amt"] and bill["vat_amt"] > 0:
        vat_line = (
            f"<div class='total-row'><span>VAT ({bill['vat_pct']}%)</span>"
            f"<span>Rs {bill['vat_amt']:,.2f}</span></div>"
        )

    sc_line = ""
    if bill["service_charge_amt"] and bill["service_charge_amt"] > 0:
        sc_line = (
            f"<div class='total-row'><span>Service charge "
            f"({bill['service_charge_pct']}%)</span>"
            f"<span>Rs {bill['service_charge_amt']:,.2f}</span></div>"
        )

    discount_line = ""
    if bill["discount_amt"] and bill["discount_amt"] > 0:
        discount_line = (
            f"<div class='total-row discount'><span>Discount</span>"
            f"<span>- Rs {bill['discount_amt']:,.2f}</span></div>"
        )

    qr_html = ""
    if settings["qr_type"] == "custom" and settings["qr_image_url"]:
        qr_html = f"""
        <div class='qr'>
            <img src='{settings['qr_image_url']}' width='120' height='120' />
            <div class='meta'>Scan to Pay</div>
        </div>"""
    elif settings["qr_type"] == "fonepay":
        qr_html = (
            "<div class='qr'>"
            "<div class='pending'>FonePay — Coming Soon</div>"
            "</div>"
        )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Courier New', monospace; width: 80mm; padding: 8px; font-size: 12px; }}
    .biz-name {{ font-size: 15px; font-weight: bold; text-align: center; margin-bottom: 2px; }}
    .header {{ text-align: center; border-bottom: 1px dashed #000; padding-bottom: 8px; margin-bottom: 6px; }}
    .bill-title {{ font-size: 14px; font-weight: bold; letter-spacing: 2px; margin: 6px 0 3px; }}
    .bill-number {{ font-size: 12px; font-weight: bold; margin: 2px 0; }}
    .meta {{ font-size: 11px; color: #333; margin: 2px 0; }}
    .bold {{ font-weight: bold; }}
    .section-label {{ font-size: 9px; text-transform: uppercase; color: #666; margin-top: 6px; margin-bottom: 1px; letter-spacing: 1px; }}
    .corporate-block {{ border: 1px dashed #ccc; padding: 5px 6px; margin: 6px 0; text-align: left; }}
    .status {{ font-weight: bold; text-transform: uppercase; font-size: 11px; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 6px 0; }}
    th {{ font-size: 10px; border-bottom: 1px solid #000; padding: 2px 0; text-align: left; }}
    td {{ font-size: 11px; padding: 3px 0; border-bottom: 0.5px solid #eee; }}
    tr:last-child td {{ border-bottom: none; }}
    .right {{ text-align: right; }}
    .totals {{ border-top: 1px dashed #000; margin-top: 6px; padding-top: 6px; }}
    .total-row {{ display: flex; justify-content: space-between; margin: 3px 0; font-size: 11px; }}
    .discount {{ color: #2a7a2a; }}
    .grand-total {{ font-weight: bold; font-size: 13px; border-top: 1px solid #000; padding-top: 5px; margin-top: 5px; }}
    .qr {{ text-align: center; margin: 10px 0; }}
    .pending {{ font-size: 10px; color: #666; padding: 8px; border: 1px dashed #ccc; }}
    .footer {{ text-align: center; border-top: 1px dashed #000; padding-top: 6px; margin-top: 8px; font-size: 10px; color: #444; }}
</style>
</head>
<body>
    <div class='header'>
        <div class='biz-name'>{biz_name}</div>
        {biz_address_line}
        {biz_phone_line}
        {biz_tax_line}
        <div style='border-top: 1px dashed #ccc; margin: 6px 0;'></div>
        <div class='bill-title'>{invoice_type}</div>
        <div class='bill-number'>{bill['bill_number']}</div>
        <div class='meta'>{table_info}</div>
        <div class='meta'>{bill_time}</div>
        {corporate_html}
        <div class='status'>{bill['status'].replace('_', ' ')}</div>
    </div>
    <table>
        <tr>
            <th>Item</th>
            <th class='right'>Qty</th>
            <th class='right'>Price</th>
            <th class='right'>Total</th>
        </tr>
        {items_html}
    </table>
    <div class='totals'>
        <div class='total-row'><span>Subtotal</span><span>Rs {bill['subtotal']:,.2f}</span></div>
        {sc_line}
        {vat_line}
        {discount_line}
        <div class='total-row grand-total'><span>TOTAL</span><span>Rs {bill['total_amount']:,.2f}</span></div>
    </div>
    {qr_html}
    <div class='footer'>
        Thank you for visiting {biz_name}<br>
        This is a computer generated invoice
    </div>
</body>
</html>"""
    return html


# Credit Accounts

async def create_credit_account(
    db, schema: str, outlet_id: UUID, data: dict
) -> dict:
    if data.get("customer_id"):
        customer = await db.fetchrow(
            f'SELECT id FROM "{schema}".customers WHERE id = $1',
            data["customer_id"]
        )
        if not customer:
            raise HTTPException(400, "Customer not found")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".credit_accounts
            (outlet_id, account_type, display_name, customer_id,
             contact_person, contact_phone, billing_email,
             credit_limit, payment_terms, notes)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        RETURNING *
        """,
        outlet_id,
        data["account_type"],
        data["display_name"],
        data.get("customer_id"),
        data.get("contact_person"),
        data.get("contact_phone"),
        data.get("billing_email"),
        data.get("credit_limit", 0),
        data.get("payment_terms", 30),
        data.get("notes"),
    )
    return dict(row)


async def list_credit_accounts(
    db, schema: str, outlet_id: UUID
) -> list[dict]:
    rows = await db.fetch(
        f"""
        SELECT * FROM "{schema}".credit_accounts
        WHERE outlet_id = $1
        ORDER BY display_name
        """,
        outlet_id
    )
    return [dict(r) for r in rows]


async def get_credit_account(
    db, schema: str, outlet_id: UUID, account_id: UUID
) -> dict:
    row = await db.fetchrow(
        f"""
        SELECT * FROM "{schema}".credit_accounts
        WHERE id = $1 AND outlet_id = $2
        """,
        account_id, outlet_id
    )
    if not row:
        raise HTTPException(404, "Credit account not found")
    return dict(row)


async def update_credit_account(
    db, schema: str, outlet_id: UUID,
    account_id: UUID, data: dict
) -> dict:
    account = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".credit_accounts
        WHERE id = $1 AND outlet_id = $2
        """,
        account_id, outlet_id
    )
    if not account:
        raise HTTPException(404, "Credit account not found")

    fields = []
    values = []
    idx = 1
    for field in ["display_name", "contact_person", "contact_phone",
                  "billing_email", "credit_limit", "payment_terms",
                  "notes", "is_active"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1

    if not fields:
        return await get_credit_account(db, schema, outlet_id, account_id)

    values.append(account_id)
    await db.execute(
        f"""
        UPDATE "{schema}".credit_accounts
        SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        """,
        *values
    )
    return await get_credit_account(db, schema, outlet_id, account_id)


async def settle_credit_account(
    db, schema: str, outlet_id: UUID,
    account_id: UUID, data: dict, processed_by: UUID
) -> dict:
    account = await db.fetchrow(
        f"""
        SELECT id, current_balance, is_active
        FROM "{schema}".credit_accounts
        WHERE id = $1 AND outlet_id = $2
        """,
        account_id, outlet_id
    )
    if not account:
        raise HTTPException(404, "Credit account not found")
    if not account["is_active"]:
        raise HTTPException(400, "Credit account is inactive")

    amount = Decimal(str(data["amount"]))
    current_balance = Decimal(str(account["current_balance"]))

    if amount > current_balance:
        raise HTTPException(
            400,
            f"Settlement amount Rs {amount} exceeds outstanding balance "
            f"Rs {current_balance}"
        )

    new_balance = current_balance - amount

    await db.execute(
        f"""
        UPDATE "{schema}".credit_accounts
        SET current_balance = $1, updated_at = NOW()
        WHERE id = $2
        """,
        new_balance, account_id
    )

    await db.execute(
        f"""
        INSERT INTO "{schema}".credit_transactions
            (credit_account_id, transaction_type, amount,
             reference, notes, processed_by)
        VALUES ($1, 'payment', $2, $3, $4, $5)
        """,
        account_id,
        amount,
        data.get("reference"),
        data.get("notes"),
        processed_by,
    )

    return await get_credit_account(db, schema, outlet_id, account_id)


async def get_credit_account_statement_html(
    db, schema: str, outlet_id: UUID, account_id: UUID
) -> str:
    account = await get_credit_account(db, schema, outlet_id, account_id)

    tenant = await db.fetchrow(
        """
        SELECT name, address, phone, pan_number, vat_registered, vat_number
        FROM core.tenants WHERE schema_name = $1
        """,
        schema
    )
    biz_name = tenant["name"] if tenant else "Restaurant"
    biz_pan = tenant["pan_number"] if tenant else None
    biz_vat = (
        tenant["vat_number"]
        if (tenant and tenant["vat_registered"]) else None
    )

    bills = await db.fetch(
        f"""
        SELECT b.id, b.bill_number, b.total_amount, b.created_at,
               o.order_number, o.order_type
        FROM "{schema}".bills b
        LEFT JOIN "{schema}".orders o ON o.id = b.order_id
        WHERE b.credit_account_id = $1
          AND b.status = 'credit_posted'
        ORDER BY b.created_at
        """,
        account_id
    )

    if not bills:
        days_html = (
            "<p style='text-align:center;color:#666;padding:20px 0;'>"
            "No outstanding bills.</p>"
        )
    else:
        days = defaultdict(list)
        for bill in bills:
            day_key = bill["created_at"].strftime("%Y-%m-%d")
            days[day_key].append(bill)

        days_html = ""
        grand_total = Decimal("0")

        for day, day_bills in sorted(days.items()):
            day_total = Decimal("0")
            day_date = datetime.strptime(day, "%Y-%m-%d").strftime("%B %d, %Y")
            day_content = ""

            for bill in day_bills:
                bill_time = bill["created_at"].strftime("%H:%M")
                bill_total = Decimal(str(bill["total_amount"]))
                day_total += bill_total
                grand_total += bill_total

                items = await db.fetch(
                    f"""
                    SELECT oi.quantity, oi.unit_price, mi.name AS item_name
                    FROM "{schema}".order_items oi
                    JOIN "{schema}".menu_items mi ON mi.id = oi.menu_item_id
                    WHERE oi.order_id = (
                        SELECT order_id FROM "{schema}".bills WHERE id = $1
                    )
                    AND oi.status != 'cancelled'
                    ORDER BY oi.created_at
                    """,
                    bill["id"]
                )

                items_html = ""
                for item in items:
                    line = Decimal(str(item["unit_price"])) * item["quantity"]
                    items_html += f"""
                    <tr>
                        <td style='padding:3px 8px;'>{item['item_name']}</td>
                        <td style='text-align:right;padding:3px 6px;'>{item['quantity']}</td>
                        <td style='text-align:right;padding:3px 6px;'>Rs {item['unit_price']:,.2f}</td>
                        <td style='text-align:right;padding:3px 6px;'>Rs {line:,.2f}</td>
                    </tr>"""

                order_label = (
                    bill['order_type'].replace('_', ' ').title()
                    if bill['order_type'] else ''
                )
                day_content += f"""
                <div style='margin:8px 0;border:0.5px solid #ddd;border-radius:4px;overflow:hidden;'>
                    <div style='background:#f5f5f5;padding:6px 10px;font-size:12px;display:flex;justify-content:space-between;'>
                        <span><strong>{bill['bill_number']}</strong> &nbsp; {order_label}</span>
                        <span style='color:#666;'>{bill_time}</span>
                    </div>
                    <table style='width:100%;border-collapse:collapse;font-size:12px;'>
                        <tr style='background:#fafafa;border-bottom:0.5px solid #eee;'>
                            <th style='text-align:left;padding:4px 8px;font-weight:400;color:#666;'>Item</th>
                            <th style='text-align:right;padding:4px 6px;font-weight:400;color:#666;'>Qty</th>
                            <th style='text-align:right;padding:4px 6px;font-weight:400;color:#666;'>Price</th>
                            <th style='text-align:right;padding:4px 6px;font-weight:400;color:#666;'>Total</th>
                        </tr>
                        {items_html}
                    </table>
                    <div style='text-align:right;padding:5px 10px;font-size:12px;border-top:0.5px solid #eee;background:#fafafa;'>
                        Bill total: <strong>Rs {bill_total:,.2f}</strong>
                    </div>
                </div>"""

            days_html += f"""
            <div style='margin:16px 0;'>
                <div style='background:#2c3e50;color:white;padding:8px 12px;font-size:13px;font-weight:bold;border-radius:4px 4px 0 0;'>
                    {day_date}
                </div>
                {day_content}
                <div style='text-align:right;padding:7px 10px;background:#ecf0f1;font-size:13px;border-radius:0 0 4px 4px;border:0.5px solid #ddd;border-top:none;'>
                    Day total: <strong>Rs {day_total:,.2f}</strong>
                </div>
            </div>"""

        days_html += f"""
        <div style='margin-top:20px;padding:12px;background:#2c3e50;color:white;border-radius:4px;display:flex;justify-content:space-between;font-size:15px;font-weight:bold;'>
            <span>Grand Total</span>
            <span>Rs {grand_total:,.2f}</span>
        </div>"""

    tax_line = ""
    if biz_vat:
        tax_line = f"VAT No: {biz_vat}"
    elif biz_pan:
        tax_line = f"PAN: {biz_pan}"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; font-size: 13px; color: #222; }}
    .biz-header {{ text-align: center; border-bottom: 2px solid #2c3e50; padding-bottom: 12px; margin-bottom: 16px; }}
    .biz-header h1 {{ font-size: 20px; margin-bottom: 4px; }}
    .biz-header p {{ font-size: 12px; color: #555; margin: 2px 0; }}
    .doc-title {{ font-size: 16px; font-weight: bold; letter-spacing: 1px; margin: 8px 0 2px; }}
    .account-info {{ background: #f8f9fa; padding: 12px 14px; border-radius: 4px; margin-bottom: 16px; border: 0.5px solid #dee2e6; }}
    .summary {{ display: flex; gap: 12px; margin-bottom: 16px; }}
    .summary-box {{ flex: 1; padding: 12px; background: #fff; border: 0.5px solid #dee2e6; border-radius: 4px; text-align: center; }}
    .summary-box .label {{ font-size: 11px; color: #666; margin-bottom: 4px; }}
    .summary-box .value {{ font-size: 17px; font-weight: bold; }}
</style>
</head>
<body>
    <div class='biz-header'>
        <h1>{biz_name}</h1>
        {f"<p>{tenant['address']}</p>" if tenant and tenant['address'] else ""}
        {f"<p>Tel: {tenant['phone']}</p>" if tenant and tenant['phone'] else ""}
        {f"<p>{tax_line}</p>" if tax_line else ""}
        <div class='doc-title'>CREDIT ACCOUNT STATEMENT</div>
    </div>
    <div class='account-info'>
        <strong>{account['display_name']}</strong> &nbsp; ({account['account_type'].title()})
        {f"<br>Contact: {account['contact_person']}" if account.get('contact_person') else ""}
        {f"<br>Email: {account['billing_email']}" if account.get('billing_email') else ""}
        <br>Payment terms: Net {account['payment_terms']} days
    </div>
    <div class='summary'>
        <div class='summary-box'>
            <div class='label'>Credit limit</div>
            <div class='value'>Rs {Decimal(str(account['credit_limit'])):,.2f}</div>
        </div>
        <div class='summary-box'>
            <div class='label'>Outstanding balance</div>
            <div class='value' style='color:#c0392b;'>Rs {Decimal(str(account['current_balance'])):,.2f}</div>
        </div>
        <div class='summary-box'>
            <div class='label'>Available credit</div>
            <div class='value' style='color:#27ae60;'>Rs {(Decimal(str(account['credit_limit'])) - Decimal(str(account['current_balance']))):,.2f}</div>
        </div>
    </div>
    <h2 style='font-size:14px;margin-bottom:10px;'>Outstanding bills by day</h2>
    {days_html}
</body>
</html>"""
    return html


async def _get_bill_line_items(
    db, schema: str, order_id: UUID
) -> list[dict]:
    rows = await db.fetch(
        f"""
        SELECT oi.id AS order_item_id, mi.name AS item_name,
               oi.quantity, oi.unit_price,
               (oi.unit_price * oi.quantity) AS line_total
        FROM "{schema}".order_items oi
        JOIN "{schema}".menu_items mi ON mi.id = oi.menu_item_id
        WHERE oi.order_id = $1 AND oi.status != 'cancelled'
        ORDER BY oi.created_at
        """,
        order_id
    )
    result = []
    for r in rows:
        d = dict(r)
        d["discount_amt"] = Decimal("0")
        result.append(d)
    return result