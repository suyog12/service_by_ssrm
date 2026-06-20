from uuid import UUID
from datetime import datetime, timedelta
from fastapi import HTTPException


# Reservations 

async def _get_unavailable_table_ids(
    db, schema: str, outlet_id: UUID,
    reserved_at: datetime, reserved_until: datetime,
    exclude_reservation_id: UUID = None
) -> set:
    """
    Returns the set of table IDs that are busy during the given window —
    either directly reserved, or merged into another reservation's anchor
    table during that window.
    """
    exclude_clause = ""
    params = [outlet_id, reserved_until, reserved_at]
    if exclude_reservation_id:
        exclude_clause = "AND r.id != $4"
        params.append(exclude_reservation_id)

    rows = await db.fetch(
        f"""
        SELECT r.id AS reservation_id, r.table_id
        FROM "{schema}".table_reservations r
        WHERE r.outlet_id = $1
          AND r.status = 'confirmed'
          AND r.reserved_at < $2
          AND ($3 < r.reserved_at + (r.duration_mins || ' minutes')::interval)
          {exclude_clause}
        """,
        *params
    )

    busy_table_ids = set()
    reservation_ids = []
    for r in rows:
        busy_table_ids.add(r["table_id"])
        reservation_ids.append(r["reservation_id"])

    if reservation_ids:
        merge_rows = await db.fetch(
            f"""
            SELECT merged_table_id
            FROM "{schema}".table_merges
            WHERE is_active = TRUE
              AND primary_table_id = ANY($1::uuid[])
            """,
            [r["table_id"] for r in rows]
        )
        for m in merge_rows:
            busy_table_ids.add(m["merged_table_id"])

    return busy_table_ids


async def _find_tables_for_party(
    db, schema: str, outlet_id: UUID, party_size: int,
    busy_table_ids: set
) -> list[dict]:
    """
    Returns a list of table rows (id, capacity) to seat the party.
    Prefers a single table that fits; otherwise greedily combines the
    smallest available tables until capacity is met.
    Raises 400 if no combination can seat the party.
    """
    rows = await db.fetch(
        f"""
        SELECT id, capacity
        FROM "{schema}".tables
        WHERE outlet_id = $1 AND status != 'occupied'
        ORDER BY capacity ASC
        """,
        outlet_id
    )
    available = [dict(r) for r in rows if r["id"] not in busy_table_ids]

    if not available:
        raise HTTPException(400, "No tables available for the requested time window")

    # Single table that fits, smallest possible
    single_fit = [t for t in available if t["capacity"] >= party_size]
    if single_fit:
        return [single_fit[0]]

    # Greedy merge — largest tables first to minimize merge count
    available_desc = sorted(available, key=lambda t: t["capacity"], reverse=True)
    combo = []
    total = 0
    for t in available_desc:
        combo.append(t)
        total += t["capacity"]
        if total >= party_size:
            return combo

    raise HTTPException(
        400,
        f"No combination of available tables can seat a party of {party_size} "
        f"in the requested time window"
    )


async def _resolve_customer(
    db, schema: str, customer_name: str, customer_phone: str
) -> UUID:
    existing = await db.fetchrow(
        f'SELECT id FROM "{schema}".customers WHERE phone = $1',
        customer_phone
    )
    if existing:
        return existing["id"]

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".customers (full_name, phone)
        VALUES ($1, $2)
        RETURNING id
        """,
        customer_name, customer_phone
    )
    return row["id"]


async def create_reservation(
    db, schema: str, outlet_id: UUID, created_by: UUID, data: dict
) -> dict:
    reserved_at = data["reserved_at"]
    reserved_until = data["reserved_until"]
    party_size = data["party_size"]

    busy_table_ids = await _get_unavailable_table_ids(
        db, schema, outlet_id, reserved_at, reserved_until
    )
    chosen_tables = await _find_tables_for_party(
        db, schema, outlet_id, party_size, busy_table_ids
    )

    customer_id = await _resolve_customer(
        db, schema, data["customer_name"], data["customer_phone"]
    )

    duration_mins = int((reserved_until - reserved_at).total_seconds() // 60)
    anchor_table = chosen_tables[0]

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".table_reservations
            (outlet_id, table_id, customer_id, customer_name, customer_phone,
             party_size, reserved_at, duration_mins, status, notes, created_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'confirmed', $9, $10)
        RETURNING *
        """,
        outlet_id,
        anchor_table["id"],
        customer_id,
        data["customer_name"],
        data["customer_phone"],
        party_size,
        reserved_at,
        duration_mins,
        data.get("notes"),
        created_by,
    )

    merged_ids = []
    for extra_table in chosen_tables[1:]:
        await db.execute(
            f"""
            INSERT INTO "{schema}".table_merges
                (primary_table_id, merged_table_id, is_active)
            VALUES ($1, $2, TRUE)
            """,
            anchor_table["id"], extra_table["id"]
        )
        merged_ids.append(extra_table["id"])

    # Mark all involved tables as reserved
    all_table_ids = [t["id"] for t in chosen_tables]
    await db.execute(
        f"""
        UPDATE "{schema}".tables
        SET status = 'reserved', updated_at = NOW()
        WHERE id = ANY($1::uuid[])
        """,
        all_table_ids
    )

    return await _hydrate_reservation(db, schema, row["id"])


async def list_reservations(
    db, schema: str, outlet_id: UUID, status: str = None
) -> list[dict]:
    if status:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".table_reservations
            WHERE outlet_id = $1 AND status = $2
            ORDER BY reserved_at
            """,
            outlet_id, status
        )
    else:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".table_reservations
            WHERE outlet_id = $1
            ORDER BY reserved_at
            """,
            outlet_id
        )
    results = []
    for r in rows:
        results.append(await _hydrate_reservation(db, schema, r["id"], row=r))
    return results


async def get_reservation(db, schema: str, outlet_id: UUID, reservation_id: UUID) -> dict:
    row = await db.fetchrow(
        f"""
        SELECT * FROM "{schema}".table_reservations
        WHERE id = $1 AND outlet_id = $2
        """,
        reservation_id, outlet_id
    )
    if not row:
        raise HTTPException(404, "Reservation not found")
    return await _hydrate_reservation(db, schema, reservation_id, row=row)


async def update_reservation(
    db, schema: str, outlet_id: UUID, reservation_id: UUID, data: dict
) -> dict:
    existing = await db.fetchrow(
        f"""
        SELECT * FROM "{schema}".table_reservations
        WHERE id = $1 AND outlet_id = $2
        """,
        reservation_id, outlet_id
    )
    if not existing:
        raise HTTPException(404, "Reservation not found")

    if existing["status"] != "confirmed" and "status" not in data:
        raise HTTPException(400, "Cannot modify a reservation that is no longer confirmed")

    new_status = data.get("status")

    fields = []
    values = []
    idx = 1
    for field in ["customer_name", "customer_phone", "party_size", "notes", "status"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1

    if fields:
        values.append(reservation_id)
        await db.execute(
            f"""
            UPDATE "{schema}".table_reservations
            SET {', '.join(fields)}, updated_at = NOW()
            WHERE id = ${idx}
            """,
            *values
        )

    if new_status in ("cancelled", "no_show", "completed"):
        await _release_tables(db, schema, reservation_id, existing["table_id"])

    return await get_reservation(db, schema, outlet_id, reservation_id)


async def seat_reservation(
    db, schema: str, outlet_id: UUID, reservation_id: UUID
) -> dict:
    """Marks the reserved table(s) as occupied — guest has arrived and is seated."""
    existing = await db.fetchrow(
        f"""
        SELECT * FROM "{schema}".table_reservations
        WHERE id = $1 AND outlet_id = $2
        """,
        reservation_id, outlet_id
    )
    if not existing:
        raise HTTPException(404, "Reservation not found")
    if existing["status"] != "confirmed":
        raise HTTPException(400, "Only confirmed reservations can be seated")

    table_ids = await _get_reservation_table_ids(db, schema, existing["table_id"])
    await db.execute(
        f"""
        UPDATE "{schema}".tables
        SET status = 'occupied', updated_at = NOW()
        WHERE id = ANY($1::uuid[])
        """,
        table_ids
    )
    return await get_reservation(db, schema, outlet_id, reservation_id)


async def _release_tables(db, schema: str, reservation_id: UUID, anchor_table_id: UUID):
    table_ids = await _get_reservation_table_ids(db, schema, anchor_table_id)

    await db.execute(
        f"""
        UPDATE "{schema}".table_merges
        SET is_active = FALSE, unmerged_at = NOW()
        WHERE primary_table_id = $1 AND is_active = TRUE
        """,
        anchor_table_id
    )

    await db.execute(
        f"""
        UPDATE "{schema}".tables
        SET status = 'available', updated_at = NOW()
        WHERE id = ANY($1::uuid[])
        """,
        table_ids
    )


async def _get_reservation_table_ids(db, schema: str, anchor_table_id: UUID) -> list:
    merge_rows = await db.fetch(
        f"""
        SELECT merged_table_id FROM "{schema}".table_merges
        WHERE primary_table_id = $1 AND is_active = TRUE
        """,
        anchor_table_id
    )
    return [anchor_table_id] + [m["merged_table_id"] for m in merge_rows]


async def _hydrate_reservation(db, schema: str, reservation_id: UUID, row=None) -> dict:
    if row is None:
        row = await db.fetchrow(
            f'SELECT * FROM "{schema}".table_reservations WHERE id = $1',
            reservation_id
        )
    result = dict(row)
    result["reserved_until"] = result["reserved_at"] + timedelta(
        minutes=result["duration_mins"] or 0
    )

    merge_rows = await db.fetch(
        f"""
        SELECT merged_table_id FROM "{schema}".table_merges
        WHERE primary_table_id = $1 AND is_active = TRUE
        """,
        result["table_id"]
    )
    result["merged_table_ids"] = [m["merged_table_id"] for m in merge_rows]
    return result