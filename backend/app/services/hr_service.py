from uuid import UUID
from decimal import Decimal
from datetime import date, datetime, timezone
from fastapi import HTTPException
import json


# HR Settings 

async def get_hr_settings(db, schema: str) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".hr_settings LIMIT 1'
    )
    if not row:
        row = await db.fetchrow(
            f'INSERT INTO "{schema}".hr_settings DEFAULT VALUES RETURNING *'
        )
    return dict(row)


async def update_hr_settings(db, schema: str, data: dict) -> dict:
    settings = await get_hr_settings(db, schema)
    fields = []
    values = []
    idx = 1
    for field in [
        "work_hours_per_day", "overtime_multiplier", "late_threshold_minutes",
        "scheme", "pf_employee_pct", "pf_employer_pct",
        "cit_employee_pct", "cit_employer_pct",
        "ssf_employee_pct", "ssf_employer_pct",
    ]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1
    if not fields:
        return settings
    values.append(settings["id"])
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".hr_settings
        SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        RETURNING *
        """,
        *values
    )
    return dict(row)


# Tax Slabs 

async def create_tax_slab(db, schema: str, data: dict) -> dict:
    existing = await db.fetchrow(
        f'SELECT id FROM "{schema}".tax_slabs WHERE fiscal_year = $1',
        data["fiscal_year"]
    )
    if existing:
        raise HTTPException(400, f"Tax slab for {data['fiscal_year']} already exists")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".tax_slabs (fiscal_year, basic_exemption, slabs)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        data["fiscal_year"],
        data["basic_exemption"],
        json.dumps(data["slabs"])
    )
    return dict(row)


async def list_tax_slabs(db, schema: str) -> list[dict]:
    rows = await db.fetch(
        f'SELECT * FROM "{schema}".tax_slabs ORDER BY fiscal_year DESC'
    )
    return [dict(r) for r in rows]


async def set_active_tax_slab(db, schema: str, slab_id: UUID) -> dict:
    row = await db.fetchrow(
        f'SELECT id FROM "{schema}".tax_slabs WHERE id = $1', slab_id
    )
    if not row:
        raise HTTPException(404, "Tax slab not found")

    await db.execute(
        f'UPDATE "{schema}".tax_slabs SET is_active = FALSE, updated_at = NOW()'
    )
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".tax_slabs
        SET is_active = TRUE, updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        slab_id
    )
    return dict(row)


async def _get_active_tax_slab(db, schema: str) -> dict | None:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".tax_slabs WHERE is_active = TRUE LIMIT 1'
    )
    return dict(row) if row else None


# Shifts 

async def create_shift(db, schema: str, data: dict) -> dict:
    existing = await db.fetchrow(
        f'SELECT id FROM "{schema}".shifts WHERE name = $1', data["name"]
    )
    if existing:
        raise HTTPException(400, f"Shift '{data['name']}' already exists")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".shifts (name, start_time, end_time)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        data["name"], data["start_time"], data["end_time"]
    )
    return dict(row)


async def list_shifts(db, schema: str) -> list[dict]:
    rows = await db.fetch(
        f'SELECT * FROM "{schema}".shifts ORDER BY start_time'
    )
    return [dict(r) for r in rows]


async def get_shift(db, schema: str, shift_id: UUID) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".shifts WHERE id = $1', shift_id
    )
    if not row:
        raise HTTPException(404, "Shift not found")
    return dict(row)


async def update_shift(db, schema: str, shift_id: UUID, data: dict) -> dict:
    await get_shift(db, schema, shift_id)
    fields = []
    values = []
    idx = 1
    for field in ["name", "start_time", "end_time", "is_active"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1
    if not fields:
        return await get_shift(db, schema, shift_id)
    values.append(shift_id)
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".shifts
        SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING *
        """,
        *values
    )
    return dict(row)


async def delete_shift(db, schema: str, shift_id: UUID) -> None:
    await get_shift(db, schema, shift_id)
    in_use = await db.fetchval(
        f'SELECT COUNT(*) FROM "{schema}".attendance WHERE shift_id = $1',
        shift_id
    )
    if in_use:
        raise HTTPException(400, "Cannot delete shift with attendance records")
    await db.execute(
        f'DELETE FROM "{schema}".shifts WHERE id = $1', shift_id
    )


# Attendance 

async def check_in(db, schema: str, user_id: UUID, data: dict) -> dict:
    existing = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".attendance
        WHERE user_id = $1 AND check_out_at IS NULL
        AND created_at::date = CURRENT_DATE
        """,
        user_id
    )
    if existing:
        raise HTTPException(400, "Already checked in today — check out first")

    settings = await get_hr_settings(db, schema)
    is_late = False
    late_minutes = 0

    if data.get("shift_id"):
        shift = await db.fetchrow(
            f'SELECT start_time FROM "{schema}".shifts WHERE id = $1',
            data["shift_id"]
        )
        if shift:
            now_time = datetime.now(timezone.utc).time()
            threshold = settings["late_threshold_minutes"]
            shift_start = shift["start_time"]
            start_minutes = shift_start.hour * 60 + shift_start.minute
            now_minutes = now_time.hour * 60 + now_time.minute
            diff = now_minutes - start_minutes
            if diff > threshold:
                is_late = True
                late_minutes = diff

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".attendance
            (user_id, shift_id, check_in_at, check_in_lat, check_in_lng,
             is_late, late_minutes, status, notes)
        VALUES ($1, $2, NOW(), $3, $4, $5, $6, 'present', $7)
        RETURNING *
        """,
        user_id,
        data.get("shift_id"),
        data.get("check_in_lat"),
        data.get("check_in_lng"),
        is_late,
        late_minutes,
        data.get("notes"),
    )
    return dict(row)


async def check_out(db, schema: str, user_id: UUID, data: dict) -> dict:
    record = await db.fetchrow(
        f"""
        SELECT a.*, s.end_time AS shift_end
        FROM "{schema}".attendance a
        LEFT JOIN "{schema}".shifts s ON s.id = a.shift_id
        WHERE a.user_id = $1 AND a.check_out_at IS NULL
        AND a.created_at::date = CURRENT_DATE
        """,
        user_id
    )
    if not record:
        raise HTTPException(400, "No active check-in found for today")

    settings = await get_hr_settings(db, schema)
    overtime_mins = 0

    if record["shift_end"]:
        now_time = datetime.now(timezone.utc).time()
        end_minutes = record["shift_end"].hour * 60 + record["shift_end"].minute
        now_minutes = now_time.hour * 60 + now_time.minute
        diff = now_minutes - end_minutes
        if diff > 0:
            overtime_mins = diff

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".attendance
        SET check_out_at = NOW(),
            check_out_lat = $1,
            check_out_lng = $2,
            overtime_mins = $3
        WHERE id = $4
        RETURNING *
        """,
        data.get("check_out_lat"),
        data.get("check_out_lng"),
        overtime_mins,
        record["id"]
    )
    return dict(row)


async def list_attendance(
    db, schema: str,
    user_id: UUID = None,
    date_from: date = None,
    date_to: date = None,
) -> list[dict]:
    conditions = []
    values = []
    idx = 1
    if user_id:
        conditions.append(f"user_id = ${idx}")
        values.append(user_id)
        idx += 1
    if date_from:
        conditions.append(f"(created_at AT TIME ZONE 'Asia/Kathmandu')::date >= ${idx}")
        values.append(date_from)
        idx += 1
    if date_to:
        conditions.append(f"(created_at AT TIME ZONE 'Asia/Kathmandu')::date <= ${idx}")
        values.append(date_to)
        idx += 1
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await db.fetch(
        f"""
        SELECT * FROM "{schema}".attendance
        {where}
        ORDER BY created_at DESC
        """,
        *values
    )
    return [dict(r) for r in rows]


async def admin_override_attendance(
    db, schema: str, data: dict, admin_id: UUID
) -> dict:
    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".attendance
            (user_id, shift_id, status, notes, created_at)
        VALUES ($1, $2, $3, $4, $5::date)
        ON CONFLICT DO NOTHING
        RETURNING *
        """,
        data["user_id"],
        data.get("shift_id"),
        data["status"],
        data.get("notes"),
        data["attendance_date"],
    )
    if not row:
        row = await db.fetchrow(
            f"""
            UPDATE "{schema}".attendance
            SET status = $1, notes = $2
            WHERE user_id = $3 AND created_at::date = $4
            RETURNING *
            """,
            data["status"],
            data.get("notes"),
            data["user_id"],
            data["attendance_date"],
        )
    return dict(row)


# Leave Types 

async def create_leave_type(db, schema: str, data: dict) -> dict:
    existing = await db.fetchrow(
        f'SELECT id FROM "{schema}".leave_types WHERE name = $1', data["name"]
    )
    if existing:
        raise HTTPException(400, f"Leave type '{data['name']}' already exists")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".leave_types (name, days_allowed, is_paid)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        data["name"], data.get("days_allowed"), data.get("is_paid", True)
    )
    return dict(row)


async def list_leave_types(db, schema: str) -> list[dict]:
    rows = await db.fetch(
        f'SELECT * FROM "{schema}".leave_types ORDER BY name'
    )
    return [dict(r) for r in rows]


async def get_leave_type(db, schema: str, leave_type_id: UUID) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".leave_types WHERE id = $1', leave_type_id
    )
    if not row:
        raise HTTPException(404, "Leave type not found")
    return dict(row)


async def update_leave_type(
    db, schema: str, leave_type_id: UUID, data: dict
) -> dict:
    await get_leave_type(db, schema, leave_type_id)
    fields = []
    values = []
    idx = 1
    for field in ["name", "days_allowed", "is_paid"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1
    if not fields:
        return await get_leave_type(db, schema, leave_type_id)
    values.append(leave_type_id)
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".leave_types
        SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING *
        """,
        *values
    )
    return dict(row)


async def delete_leave_type(db, schema: str, leave_type_id: UUID) -> None:
    await get_leave_type(db, schema, leave_type_id)
    in_use = await db.fetchval(
        f'SELECT COUNT(*) FROM "{schema}".leave_requests WHERE leave_type_id = $1',
        leave_type_id
    )
    if in_use:
        raise HTTPException(400, "Cannot delete leave type with existing requests")
    await db.execute(
        f'DELETE FROM "{schema}".leave_types WHERE id = $1', leave_type_id
    )


# Leave Requests 

async def create_leave_request(
    db, schema: str, user_id: UUID, data: dict
) -> dict:
    await get_leave_type(db, schema, data["leave_type_id"])

    if data["end_date"] < data["start_date"]:
        raise HTTPException(400, "end_date must be on or after start_date")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".leave_requests
            (user_id, leave_type_id, start_date, end_date, reason)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        user_id,
        data["leave_type_id"],
        data["start_date"],
        data["end_date"],
        data.get("reason"),
    )
    return dict(row)


async def list_leave_requests(
    db, schema: str,
    user_id: UUID = None,
    status: str = None,
) -> list[dict]:
    conditions = []
    values = []
    idx = 1
    if user_id:
        conditions.append(f"lr.user_id = ${idx}")
        values.append(user_id)
        idx += 1
    if status:
        conditions.append(f"lr.status = ${idx}")
        values.append(status)
        idx += 1
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await db.fetch(
        f"""
        SELECT lr.*, lt.name AS leave_type_name
        FROM "{schema}".leave_requests lr
        JOIN "{schema}".leave_types lt ON lt.id = lr.leave_type_id
        {where}
        ORDER BY lr.created_at DESC
        """,
        *values
    )
    return [dict(r) for r in rows]


async def review_leave_request(
    db, schema: str, request_id: UUID, reviewer_id: UUID, status: str
) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".leave_requests WHERE id = $1', request_id
    )
    if not row:
        raise HTTPException(404, "Leave request not found")
    if row["status"] != "pending":
        raise HTTPException(400, f"Leave request is already {row['status']}")

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".leave_requests
        SET status = $1, reviewed_by = $2, reviewed_at = NOW()
        WHERE id = $3
        RETURNING *
        """,
        status, reviewer_id, request_id
    )
    return dict(row)


async def cancel_leave_request(
    db, schema: str, request_id: UUID, user_id: UUID
) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".leave_requests WHERE id = $1 AND user_id = $2',
        request_id, user_id
    )
    if not row:
        raise HTTPException(404, "Leave request not found")
    if row["status"] not in ("pending",):
        raise HTTPException(400, "Only pending requests can be cancelled")

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".leave_requests
        SET status = 'cancelled'
        WHERE id = $1
        RETURNING *
        """,
        request_id
    )
    return dict(row)


# Payroll 

def _calculate_income_tax(annual_taxable: Decimal, slabs: list) -> Decimal:
    tax = Decimal("0")
    for slab in slabs:
        rate = Decimal(str(slab["rate"]))
        slab_min = Decimal(str(slab["min"]))
        slab_max = Decimal(str(slab["max"])) if slab["max"] is not None else None

        if annual_taxable <= slab_min:
            break

        if slab_max is None:
            taxable_in_slab = annual_taxable - slab_min
        else:
            taxable_in_slab = min(annual_taxable, slab_max) - slab_min

        if taxable_in_slab > 0:
            tax += taxable_in_slab * rate

    return tax.quantize(Decimal("0.01"))


async def create_payroll_period(db, schema: str, data: dict) -> dict:
    if data["end_date"] < data["start_date"]:
        raise HTTPException(400, "end_date must be after start_date")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".payroll_periods
            (period_name, start_date, end_date)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        data["period_name"], data["start_date"], data["end_date"]
    )
    return dict(row)


async def list_payroll_periods(db, schema: str) -> list[dict]:
    rows = await db.fetch(
        f'SELECT * FROM "{schema}".payroll_periods ORDER BY start_date DESC'
    )
    return [dict(r) for r in rows]


async def get_payroll_period(db, schema: str, period_id: UUID) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".payroll_periods WHERE id = $1', period_id
    )
    if not row:
        raise HTTPException(404, "Payroll period not found")
    return dict(row)


async def process_payroll(
    db, schema: str, period_id: UUID, processed_by: UUID
) -> list[dict]:
    period = await get_payroll_period(db, schema, period_id)
    if period["status"] != "draft":
        raise HTTPException(400, f"Payroll period is already {period['status']}")

    settings = await get_hr_settings(db, schema)
    tax_slab = await _get_active_tax_slab(db, schema)
    scheme = settings.get("scheme", "pf")

    # Fetch all active staff with salary info
    profiles = await db.fetch(
        f"""
        SELECT up.id AS user_id, up.base_salary, up.salary_type
        FROM "{schema}".user_profiles up
        WHERE up.base_salary IS NOT NULL AND up.date_left IS NULL
        """
    )

    period_start = period["start_date"]
    period_end = period["end_date"]
    work_days_in_month = Decimal(str(settings["work_hours_per_day"])) * Decimal("30") / Decimal(str(settings["work_hours_per_day"]))
    work_days_in_month = Decimal("26")  # standard Nepal working days per month

    entries = []
    for profile in profiles:
        user_id = profile["user_id"]
        base_salary = Decimal(str(profile["base_salary"]))

        # Count days worked from attendance
        days_worked = await db.fetchval(
            f"""
            SELECT COUNT(*) FROM "{schema}".attendance
            WHERE user_id = $1
              AND created_at::date BETWEEN $2 AND $3
              AND status IN ('present', 'half_day')
            """,
            user_id, period_start, period_end
        ) or 0

        half_days = await db.fetchval(
            f"""
            SELECT COUNT(*) FROM "{schema}".attendance
            WHERE user_id = $1
              AND created_at::date BETWEEN $2 AND $3
              AND status = 'half_day'
            """,
            user_id, period_start, period_end
        ) or 0

        days_worked_dec = Decimal(str(days_worked)) - (Decimal(str(half_days)) * Decimal("0.5"))

        # Overtime
        total_overtime_mins = await db.fetchval(
            f"""
            SELECT COALESCE(SUM(overtime_mins), 0)
            FROM "{schema}".attendance
            WHERE user_id = $1
              AND created_at::date BETWEEN $2 AND $3
            """,
            user_id, period_start, period_end
        ) or 0

        overtime_hours = Decimal(str(total_overtime_mins)) / Decimal("60")
        hourly_rate = base_salary / (work_days_in_month * Decimal(str(settings["work_hours_per_day"])))
        overtime_pay = (overtime_hours * hourly_rate * Decimal(str(settings["overtime_multiplier"]))).quantize(Decimal("0.01"))

        # Gross pay
        daily_rate = base_salary / work_days_in_month
        gross_pay = (daily_rate * days_worked_dec + overtime_pay).quantize(Decimal("0.01"))

        # PF / SSF / CIT
        pf_employee = Decimal("0")
        pf_employer = Decimal("0")
        cit_employee = Decimal("0")
        cit_employer = Decimal("0")
        ssf_employee = Decimal("0")
        ssf_employer = Decimal("0")

        if scheme in ("pf", "both"):
            pf_employee = (gross_pay * Decimal(str(settings["pf_employee_pct"])) / 100).quantize(Decimal("0.01"))
            pf_employer = (gross_pay * Decimal(str(settings["pf_employer_pct"])) / 100).quantize(Decimal("0.01"))
            cit_employee = (gross_pay * Decimal(str(settings["cit_employee_pct"])) / 100).quantize(Decimal("0.01"))
            cit_employer = (gross_pay * Decimal(str(settings["cit_employer_pct"])) / 100).quantize(Decimal("0.01"))

        if scheme in ("ssf", "both"):
            ssf_employee = (gross_pay * Decimal(str(settings["ssf_employee_pct"])) / 100).quantize(Decimal("0.01"))
            ssf_employer = (gross_pay * Decimal(str(settings["ssf_employer_pct"])) / 100).quantize(Decimal("0.01"))

        # Income tax — Nepal progressive slab
        annual_gross = gross_pay * 12
        annual_pf_cit = (pf_employee + cit_employee) * 12
        basic_exemption = Decimal(str(tax_slab["basic_exemption"])) if tax_slab else Decimal("500000")
        annual_taxable = max(Decimal("0"), annual_gross - annual_pf_cit - basic_exemption)

        monthly_tax = Decimal("0")
        if tax_slab:
            slabs = tax_slab["slabs"] if isinstance(tax_slab["slabs"], list) else json.loads(tax_slab["slabs"])
            annual_tax = _calculate_income_tax(annual_taxable, slabs)
            monthly_tax = (annual_tax / 12).quantize(Decimal("0.01"))

        total_deductions = pf_employee + cit_employee + ssf_employee + monthly_tax
        net_pay = (gross_pay - total_deductions).quantize(Decimal("0.01"))

        entry = await db.fetchrow(
            f"""
            INSERT INTO "{schema}".payroll_entries
                (period_id, user_id, base_salary, days_worked, overtime_hours,
                 overtime_pay, gross_pay, pf_employee, pf_employer,
                 cit_employee, cit_employer, ssf_employee, ssf_employer,
                 taxable_income, income_tax, deductions, net_pay)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
            ON CONFLICT DO NOTHING
            RETURNING *
            """,
            period_id, user_id, base_salary, days_worked_dec, overtime_hours,
            overtime_pay, gross_pay, pf_employee, pf_employer,
            cit_employee, cit_employer, ssf_employee, ssf_employer,
            annual_taxable / 12, monthly_tax, total_deductions, net_pay
        )
        if entry:
            entries.append(dict(entry))

    await db.execute(
        f"""
        UPDATE "{schema}".payroll_periods
        SET status = 'processing', processed_by = $1
        WHERE id = $2
        """,
        processed_by, period_id
    )
    return entries


async def list_payroll_entries(
    db, schema: str, period_id: UUID
) -> list[dict]:
    rows = await db.fetch(
        f"""
        SELECT * FROM "{schema}".payroll_entries
        WHERE period_id = $1
        ORDER BY created_at
        """,
        period_id
    )
    return [dict(r) for r in rows]


async def update_payroll_entry(
    db, schema: str, entry_id: UUID, data: dict
) -> dict:
    entry = await db.fetchrow(
        f"""
        SELECT pe.*, pp.status AS period_status
        FROM "{schema}".payroll_entries pe
        JOIN "{schema}".payroll_periods pp ON pp.id = pe.period_id
        WHERE pe.id = $1
        """,
        entry_id
    )
    if not entry:
        raise HTTPException(404, "Payroll entry not found")
    if entry["period_status"] == "paid":
        raise HTTPException(400, "Cannot edit a paid payroll entry")

    bonuses = Decimal(str(data.get("bonuses", entry["bonuses"] or 0)))
    deductions = Decimal(str(data.get("deductions", entry["deductions"] or 0)))
    gross = Decimal(str(entry["gross_pay"] or 0))
    income_tax = Decimal(str(entry["income_tax"] or 0))
    pf_emp = Decimal(str(entry["pf_employee"] or 0))
    cit_emp = Decimal(str(entry["cit_employee"] or 0))
    ssf_emp = Decimal(str(entry["ssf_employee"] or 0))
    net_pay = (gross + bonuses - pf_emp - cit_emp - ssf_emp - income_tax - deductions).quantize(Decimal("0.01"))

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".payroll_entries
        SET bonuses = $1, deductions = $2, net_pay = $3, notes = $4
        WHERE id = $5
        RETURNING *
        """,
        bonuses, deductions, net_pay,
        data.get("notes", entry["notes"]),
        entry_id
    )
    return dict(row)


async def approve_payroll(db, schema: str, period_id: UUID) -> dict:
    period = await get_payroll_period(db, schema, period_id)
    if period["status"] != "processing":
        raise HTTPException(400, "Payroll must be in processing state to approve")

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".payroll_periods
        SET status = 'approved'
        WHERE id = $1
        RETURNING *
        """,
        period_id
    )
    return dict(row)


async def mark_payroll_paid(db, schema: str, period_id: UUID) -> dict:
    period = await get_payroll_period(db, schema, period_id)
    if period["status"] != "approved":
        raise HTTPException(400, "Payroll must be approved before marking as paid")

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".payroll_periods
        SET status = 'paid'
        WHERE id = $1
        RETURNING *
        """,
        period_id
    )
    return dict(row)


# Shift Handovers 

async def create_handover(
    db, schema: str, outgoing_user_id: UUID, data: dict
) -> dict:
    incoming = await db.fetchrow(
        f'SELECT id FROM "{schema}".user_profiles WHERE id = $1',
        data["incoming_user_id"]
    )
    if not incoming:
        raise HTTPException(404, "Incoming user not found")

    # Snapshot open tables and pending orders
    open_tables = await db.fetch(
        f"""
        SELECT id, table_number, status FROM "{schema}".tables
        WHERE status IN ('occupied', 'reserved')
        """
    )
    pending_orders = await db.fetch(
        f"""
        SELECT id, order_number, status FROM "{schema}".orders
        WHERE status IN ('open', 'in_progress')
        """
    )

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".shift_handovers
            (outgoing_user_id, incoming_user_id, shift_id,
             notes, cash_amount, incidents,
             open_tables, pending_orders)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        outgoing_user_id,
        data["incoming_user_id"],
        data.get("shift_id"),
        data.get("notes"),
        data.get("cash_amount"),
        data.get("incidents"),
        json.dumps([dict(t) for t in open_tables]),
        json.dumps([dict(o) for o in pending_orders]),
    )
    return dict(row)


async def list_handovers(
    db, schema: str, user_id: UUID = None
) -> list[dict]:
    if user_id:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".shift_handovers
            WHERE outgoing_user_id = $1 OR incoming_user_id = $1
            ORDER BY created_at DESC
            """,
            user_id
        )
    else:
        rows = await db.fetch(
            f'SELECT * FROM "{schema}".shift_handovers ORDER BY created_at DESC'
        )
    return [dict(r) for r in rows]


async def acknowledge_handover(
    db, schema: str, handover_id: UUID, user_id: UUID
) -> dict:
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".shift_handovers WHERE id = $1',
        handover_id
    )
    if not row:
        raise HTTPException(404, "Handover not found")
    if str(row["incoming_user_id"]) != str(user_id):
        raise HTTPException(403, "Only the incoming user can acknowledge this handover")
    if row["acknowledged"]:
        raise HTTPException(400, "Handover already acknowledged")

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".shift_handovers
        SET acknowledged = TRUE, acknowledged_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        handover_id
    )
    return dict(row)