import asyncpg
from uuid import UUID
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from app.schemas.hotel import (
    RoomTypeCreate, RoomTypeUpdate,
    PricingRuleCreate,
    RoomCreate, RoomUpdate,
    GuestCreate, GuestUpdate,
    ReservationCreate, ReservationUpdate,
)
from fastapi import HTTPException
from app.utils.nepali_date import to_bs, add_bs_fields


_RESERVATION_DATE_FIELDS = [
    "check_in_date", "check_out_date",
    "actual_check_in", "actual_check_out", "created_at"
]


# Room Types 

async def create_room_type(
    data: RoomTypeCreate,
    schema: str,
    db: asyncpg.Connection
):
    valid_bed_types = {"single", "double", "twin", "king", "queen"}
    valid_view_types = {"mountain", "garden", "city", "pool", "courtyard", "none"}

    if data.bed_type and data.bed_type not in valid_bed_types:
        raise HTTPException(status_code=422, detail=f"Invalid bed_type. Must be one of: {', '.join(valid_bed_types)}")
    if data.view_type and data.view_type not in valid_view_types:
        raise HTTPException(status_code=422, detail=f"Invalid view_type. Must be one of: {', '.join(valid_view_types)}")

    existing = await db.fetchrow(
        f'SELECT id FROM "{schema}".room_types WHERE name = $1',
        data.name
    )
    if existing:
        raise HTTPException(status_code=400, detail="A room type with this name already exists")

    import json
    amenities_json = json.dumps(data.amenities) if data.amenities is not None else None

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".room_types
            (name, description, base_price, capacity, max_adults, max_children,
             bed_type, floor_area_sqm, view_type, amenities, image_urls)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11)
        RETURNING *
        """,
        data.name,
        data.description,
        data.base_price,
        data.capacity,
        data.max_adults,
        data.max_children,
        data.bed_type,
        data.floor_area_sqm,
        data.view_type or "none",
        amenities_json,
        data.image_urls,
    )
    return dict(row)


async def list_room_types(schema: str, db: asyncpg.Connection, active_only: bool = True):
    query = f'SELECT * FROM "{schema}".room_types'
    if active_only:
        query += " WHERE is_active = TRUE"
    query += " ORDER BY name"
    rows = await db.fetch(query)
    return [dict(r) for r in rows]


async def get_room_type(room_type_id: UUID, schema: str, db: asyncpg.Connection):
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".room_types WHERE id = $1',
        room_type_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Room type not found")
    return dict(row)


async def update_room_type(
    room_type_id: UUID,
    data: RoomTypeUpdate,
    schema: str,
    db: asyncpg.Connection
):
    existing = await get_room_type(room_type_id, schema, db)

    valid_bed_types = {"single", "double", "twin", "king", "queen"}
    valid_view_types = {"mountain", "garden", "city", "pool", "courtyard", "none"}

    if data.bed_type and data.bed_type not in valid_bed_types:
        raise HTTPException(status_code=422, detail=f"Invalid bed_type")
    if data.view_type and data.view_type not in valid_view_types:
        raise HTTPException(status_code=422, detail=f"Invalid view_type")

    if data.name and data.name != existing["name"]:
        dup = await db.fetchrow(
            f'SELECT id FROM "{schema}".room_types WHERE name = $1 AND id != $2',
            data.name, room_type_id
        )
        if dup:
            raise HTTPException(status_code=400, detail="A room type with this name already exists")

    import json
    fields = []
    values = []
    i = 1

    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        if key == "amenities":
            fields.append(f"{key} = ${i}::jsonb")
            values.append(json.dumps(val) if val is not None else None)
        else:
            fields.append(f"{key} = ${i}")
            values.append(val)
        i += 1

    if not fields:
        return existing

    fields.append(f"updated_at = ${i}")
    values.append(datetime.now(timezone.utc))
    values.append(room_type_id)

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".room_types
        SET {', '.join(fields)}
        WHERE id = ${i + 1}
        RETURNING *
        """,
        *values
    )
    return dict(row)


async def delete_room_type(room_type_id: UUID, schema: str, db: asyncpg.Connection):
    await get_room_type(room_type_id, schema, db)
    rooms = await db.fetchrow(
        f'SELECT id FROM "{schema}".rooms WHERE room_type_id = $1 LIMIT 1',
        room_type_id
    )
    if rooms:
        raise HTTPException(status_code=400, detail="Cannot delete room type with existing rooms")
    await db.execute(
        f'DELETE FROM "{schema}".room_types WHERE id = $1',
        room_type_id
    )
    return {"message": "Room type deleted successfully"}


# Pricing Rules 

async def create_pricing_rule(
    room_type_id: UUID,
    data: PricingRuleCreate,
    schema: str,
    db: asyncpg.Connection
):
    await get_room_type(room_type_id, schema, db)
    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".pricing_rules
            (room_type_id, name, price, start_date, end_date, days_of_week, is_active)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
        """,
        room_type_id,
        data.name,
        data.price,
        data.start_date,
        data.end_date,
        data.days_of_week,
        data.is_active,
    )
    return dict(row)


async def list_pricing_rules(room_type_id: UUID, schema: str, db: asyncpg.Connection):
    await get_room_type(room_type_id, schema, db)
    rows = await db.fetch(
        f'SELECT * FROM "{schema}".pricing_rules WHERE room_type_id = $1 ORDER BY created_at',
        room_type_id
    )
    return [dict(r) for r in rows]


async def delete_pricing_rule(rule_id: UUID, schema: str, db: asyncpg.Connection):
    row = await db.fetchrow(
        f'SELECT id FROM "{schema}".pricing_rules WHERE id = $1',
        rule_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Pricing rule not found")
    await db.execute(f'DELETE FROM "{schema}".pricing_rules WHERE id = $1', rule_id)
    return {"message": "Pricing rule deleted"}


# Rooms 

async def create_room(data: RoomCreate, schema: str, db: asyncpg.Connection):
    await get_room_type(data.room_type_id, schema, db)

    existing = await db.fetchrow(
        f'SELECT id FROM "{schema}".rooms WHERE room_number = $1',
        data.room_number
    )
    if existing:
        raise HTTPException(status_code=400, detail="A room with this number already exists")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".rooms (room_type_id, room_number, floor, notes)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        data.room_type_id,
        data.room_number,
        data.floor,
        data.notes,
    )
    return dict(row)


async def list_rooms(
    schema: str,
    db: asyncpg.Connection,
    room_type_id: Optional[UUID] = None,
    status: Optional[str] = None
):
    conditions = []
    values = []
    i = 1

    if room_type_id:
        conditions.append(f"room_type_id = ${i}")
        values.append(room_type_id)
        i += 1
    if status:
        conditions.append(f"status = ${i}")
        values.append(status)
        i += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await db.fetch(
        f'SELECT * FROM "{schema}".rooms {where} ORDER BY room_number',
        *values
    )
    return [dict(r) for r in rows]


async def get_room(room_id: UUID, schema: str, db: asyncpg.Connection):
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".rooms WHERE id = $1',
        room_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Room not found")
    return dict(row)


async def update_room(
    room_id: UUID,
    data: RoomUpdate,
    schema: str,
    db: asyncpg.Connection
):
    await get_room(room_id, schema, db)

    valid_statuses = {"available", "occupied", "cleaning", "maintenance", "reserved"}
    if data.status and data.status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"Invalid status")

    fields = []
    values = []
    i = 1

    for key, val in data.model_dump(exclude_unset=True).items():
        fields.append(f"{key} = ${i}")
        values.append(val)
        i += 1

    if not fields:
        return await get_room(room_id, schema, db)

    fields.append(f"updated_at = ${i}")
    values.append(datetime.now(timezone.utc))
    values.append(room_id)

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".rooms
        SET {', '.join(fields)}
        WHERE id = ${i + 1}
        RETURNING *
        """,
        *values
    )
    return dict(row)


async def delete_room(room_id: UUID, schema: str, db: asyncpg.Connection):
    room = await get_room(room_id, schema, db)
    if room["status"] != "available":
        raise HTTPException(status_code=400, detail="Cannot delete a room that is not available")
    active = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".hotel_reservations
        WHERE room_id = $1 AND status IN ('confirmed', 'checked_in')
        LIMIT 1
        """,
        room_id
    )
    if active:
        raise HTTPException(status_code=400, detail="Cannot delete a room with active reservations")
    await db.execute(f'DELETE FROM "{schema}".rooms WHERE id = $1', room_id)
    return {"message": "Room deleted successfully"}


# Availability 

async def check_availability(
    check_in: date,
    check_out: date,
    adults: int,
    children: int,
    schema: str,
    db: asyncpg.Connection
):
    if check_out <= check_in:
        raise HTTPException(status_code=422, detail="Check-out date must be after check-in date")

    total_nights = (check_out - check_in).days

    room_types = await db.fetch(
        f"""
        SELECT * FROM "{schema}".room_types
        WHERE is_active = TRUE
          AND max_adults >= $1
        ORDER BY base_price
        """,
        adults
    )

    result = []
    for rt in room_types:
        occupied_room_ids = await db.fetch(
            f"""
            SELECT DISTINCT room_id FROM "{schema}".hotel_reservations
            WHERE status IN ('confirmed', 'checked_in')
              AND check_in_date < $1
              AND check_out_date > $2
            """,
            check_out, check_in
        )
        occupied_ids = {r["room_id"] for r in occupied_room_ids}

        available_rooms = await db.fetch(
            f"""
            SELECT * FROM "{schema}".rooms
            WHERE room_type_id = $1
              AND status NOT IN ('maintenance', 'cleaning')
              AND id != ALL($2::uuid[])
            ORDER BY room_number
            """,
            rt["id"],
            list(occupied_ids) if occupied_ids else []
        )

        if not available_rooms:
            continue

        price_rule = await db.fetchrow(
            f"""
            SELECT price FROM "{schema}".pricing_rules
            WHERE room_type_id = $1
              AND is_active = TRUE
              AND (start_date IS NULL OR start_date <= $2)
              AND (end_date IS NULL OR end_date >= $3)
            ORDER BY start_date DESC NULLS LAST
            LIMIT 1
            """,
            rt["id"], check_in, check_out
        )
        price_per_night = price_rule["price"] if price_rule else rt["base_price"]
        price_for_stay = price_per_night * total_nights

        result.append({
            "room_type_id": rt["id"],
            "name": rt["name"],
            "description": rt["description"],
            "base_price": rt["base_price"],
            "price_for_stay": price_for_stay,
            "total_nights": total_nights,
            "max_adults": rt["max_adults"],
            "max_children": rt["max_children"],
            "bed_type": rt["bed_type"],
            "view_type": rt["view_type"],
            "amenities": rt["amenities"],
            "image_urls": rt["image_urls"],
            "available_rooms": len(available_rooms),
            "rooms": [dict(r) for r in available_rooms],
        })

    return result


# Guests 

async def create_guest(data: GuestCreate, schema: str, db: asyncpg.Connection):
    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".guests
            (full_name, phone, email, id_type, id_number,
             nationality, company_name, company_pan, is_corporate)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING *
        """,
        data.full_name,
        data.phone,
        data.email,
        data.id_type,
        data.id_number,
        data.nationality,
        data.company_name,
        data.company_pan,
        data.is_corporate,
    )
    return dict(row)


async def list_guests(schema: str, db: asyncpg.Connection, search: Optional[str] = None):
    if search:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".guests
            WHERE full_name ILIKE $1 OR phone ILIKE $1
            ORDER BY full_name
            """,
            f"%{search}%"
        )
    else:
        rows = await db.fetch(
            f'SELECT * FROM "{schema}".guests ORDER BY full_name'
        )
    return [dict(r) for r in rows]


async def get_guest(guest_id: UUID, schema: str, db: asyncpg.Connection):
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".guests WHERE id = $1',
        guest_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Guest not found")
    return dict(row)


async def update_guest(
    guest_id: UUID,
    data: GuestUpdate,
    schema: str,
    db: asyncpg.Connection
):
    await get_guest(guest_id, schema, db)

    fields = []
    values = []
    i = 1

    for key, val in data.model_dump(exclude_unset=True).items():
        fields.append(f"{key} = ${i}")
        values.append(val)
        i += 1

    if not fields:
        return await get_guest(guest_id, schema, db)

    fields.append(f"updated_at = ${i}")
    values.append(datetime.now(timezone.utc))
    values.append(guest_id)

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".guests
        SET {', '.join(fields)}
        WHERE id = ${i + 1}
        RETURNING *
        """,
        *values
    )
    return dict(row)


# Reservations 

async def create_reservation(
    data: ReservationCreate,
    schema: str,
    db: asyncpg.Connection,
    created_by: UUID
):
    valid_sources = {
        "direct", "phone", "whatsapp", "email", "website",
        "booking_com", "expedia", "agoda", "airbnb",
        "travel_agent", "corporate", "other"
    }
    valid_meal_plans = {
        "room_only", "bed_breakfast", "half_board", "full_board", "all_inclusive"
    }

    if str(data.booking_source) not in valid_sources:
        raise HTTPException(status_code=422, detail=f"Invalid booking_source")
    if str(data.meal_plan) not in valid_meal_plans:
        raise HTTPException(status_code=422, detail=f"Invalid meal_plan")
    if data.check_out_date <= data.check_in_date:
        raise HTTPException(status_code=422, detail="Check-out must be after check-in")

    await get_room(data.room_id, schema, db)
    await get_guest(data.guest_id, schema, db)

    conflict = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".hotel_reservations
        WHERE room_id = $1
          AND status IN ('confirmed', 'checked_in')
          AND check_in_date < $2
          AND check_out_date > $3
        """,
        data.room_id, data.check_out_date, data.check_in_date
    )
    if conflict:
        raise HTTPException(status_code=400, detail="Room is not available for the selected dates")

    total_nights = (data.check_out_date - data.check_in_date).days
    total_amount = data.rate_per_night * total_nights

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".hotel_reservations
            (room_id, guest_id, check_in_date, check_out_date,
             adults, children, rate_per_night, advance_deposit,
             booking_source, booking_reference, commission_pct,
             meal_plan, total_nights, total_amount,
             special_requests, notes, created_by)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
        RETURNING *
        """,
        data.room_id,
        data.guest_id,
        data.check_in_date,
        data.check_out_date,
        data.adults,
        data.children,
        data.rate_per_night,
        data.advance_deposit,
        data.booking_source,
        data.booking_reference,
        data.commission_pct,
        data.meal_plan,
        total_nights,
        total_amount,
        data.special_requests,
        data.notes,
        created_by,
    )

    await db.execute(
        f'UPDATE "{schema}".rooms SET status = \'reserved\', updated_at = NOW() WHERE id = $1',
        data.room_id
    )

    return add_bs_fields(dict(row), _RESERVATION_DATE_FIELDS)


async def list_reservations(
    schema: str,
    db: asyncpg.Connection,
    status: Optional[str] = None,
    guest_id: Optional[UUID] = None
):
    conditions = []
    values = []
    i = 1

    if status:
        conditions.append(f"status = ${i}")
        values.append(status)
        i += 1
    if guest_id:
        conditions.append(f"guest_id = ${i}")
        values.append(guest_id)
        i += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await db.fetch(
        f"""
        SELECT * FROM "{schema}".hotel_reservations
        {where}
        ORDER BY check_in_date DESC
        """,
        *values
    )
    return [add_bs_fields(dict(r), _RESERVATION_DATE_FIELDS) for r in rows]


async def get_reservation(reservation_id: UUID, schema: str, db: asyncpg.Connection):
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".hotel_reservations WHERE id = $1',
        reservation_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return add_bs_fields(dict(row), _RESERVATION_DATE_FIELDS)


async def update_reservation(
    reservation_id: UUID,
    data: ReservationUpdate,
    schema: str,
    db: asyncpg.Connection
):
    await get_reservation(reservation_id, schema, db)

    valid_statuses = {"confirmed", "checked_in", "checked_out", "cancelled", "no_show"}
    if data.status and data.status not in valid_statuses:
        raise HTTPException(status_code=422, detail="Invalid status")

    fields = []
    values = []
    i = 1

    for key, val in data.model_dump(exclude_unset=True).items():
        fields.append(f"{key} = ${i}")
        values.append(val)
        i += 1

    if not fields:
        return await get_reservation(reservation_id, schema, db)

    fields.append(f"updated_at = ${i}")
    values.append(datetime.now(timezone.utc))
    values.append(reservation_id)

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".hotel_reservations
        SET {', '.join(fields)}
        WHERE id = ${i + 1}
        RETURNING *
        """,
        *values
    )
    return add_bs_fields(dict(row), _RESERVATION_DATE_FIELDS)


async def cancel_reservation(reservation_id: UUID, schema: str, db: asyncpg.Connection):
    res = await get_reservation(reservation_id, schema, db)
    if res["status"] not in ("confirmed",):
        raise HTTPException(status_code=400, detail="Only confirmed reservations can be cancelled")

    await db.execute(
        f"""
        UPDATE "{schema}".hotel_reservations
        SET status = 'cancelled', updated_at = NOW()
        WHERE id = $1
        """,
        reservation_id
    )
    await db.execute(
        f"UPDATE \"{schema}\".rooms SET status = 'available', updated_at = NOW() WHERE id = $1",
        res["room_id"]
    )
    return {"message": "Reservation cancelled"}


# Check In / Check Out 

async def check_in(reservation_id: UUID, schema: str, db: asyncpg.Connection):
    res = await get_reservation(reservation_id, schema, db)
    if res["status"] != "confirmed":
        raise HTTPException(status_code=400, detail="Only confirmed reservations can be checked in")

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".hotel_reservations
        SET status = 'checked_in',
            actual_check_in = NOW(),
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        reservation_id
    )
    await db.execute(
        f"UPDATE \"{schema}\".rooms SET status = 'occupied', updated_at = NOW() WHERE id = $1",
        res["room_id"]
    )

    await db.execute(
        f"""
        INSERT INTO "{schema}".guest_folio
            (reservation_id, charge_type, description, amount)
        SELECT $1, 'room_night', 'Room charge: ' || r.check_in_date || ' to ' || r.check_out_date, r.total_amount
        FROM "{schema}".hotel_reservations r
        WHERE r.id = $1
        """,
        reservation_id
    )

    return add_bs_fields(dict(row), _RESERVATION_DATE_FIELDS)


async def check_out(reservation_id: UUID, schema: str, db: asyncpg.Connection):
    res = await get_reservation(reservation_id, schema, db)
    if res["status"] != "checked_in":
        raise HTTPException(status_code=400, detail="Only checked-in reservations can be checked out")

    folio_total = await db.fetchval(
        f"""
        SELECT COALESCE(SUM(amount), 0)
        FROM "{schema}".guest_folio
        WHERE reservation_id = $1 AND is_void = FALSE
        """,
        reservation_id
    )

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".hotel_reservations
        SET status = 'checked_out',
            actual_check_out = NOW(),
            total_amount = $2,
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        reservation_id,
        folio_total
    )
    await db.execute(
        f"UPDATE \"{schema}\".rooms SET status = 'cleaning', updated_at = NOW() WHERE id = $1",
        res["room_id"]
    )

    return {
        "reservation": add_bs_fields(dict(row), _RESERVATION_DATE_FIELDS),
        "total_charged": float(folio_total)
    }


# Guest Folio 

async def get_folio(reservation_id: UUID, schema: str, db: asyncpg.Connection):
    await get_reservation(reservation_id, schema, db)
    rows = await db.fetch(
        f"""
        SELECT * FROM "{schema}".guest_folio
        WHERE reservation_id = $1
        ORDER BY created_at
        """,
        reservation_id
    )
    total = sum(r["amount"] for r in rows if not r["is_void"])
    return {"entries": [dict(r) for r in rows], "total": float(total)}


async def add_folio_charge(
    reservation_id: UUID,
    charge_type: str,
    description: str,
    amount: Decimal,
    schema: str,
    db: asyncpg.Connection,
    posted_by: UUID,
    reference_id: Optional[UUID] = None,
    reference_type: Optional[str] = None
):
    res = await get_reservation(reservation_id, schema, db)
    if res["status"] != "checked_in":
        raise HTTPException(status_code=400, detail="Can only add charges to checked-in reservations")

    valid_charge_types = {
        "room_night", "restaurant", "bar", "room_service",
        "minibar", "laundry", "telephone", "spa", "other"
    }
    if charge_type not in valid_charge_types:
        raise HTTPException(status_code=422, detail="Invalid charge type")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".guest_folio
            (reservation_id, charge_type, description, amount,
             reference_id, reference_type, posted_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
        """,
        reservation_id,
        charge_type,
        description,
        amount,
        reference_id,
        reference_type,
        posted_by,
    )
    return dict(row)


# Room Share Card 

async def get_room_share_card(
    room_type_id: UUID,
    schema: str,
    db: asyncpg.Connection,
    check_in: Optional[date] = None,
    check_out: Optional[date] = None
):
    rt = await get_room_type(room_type_id, schema, db)

    available_count = 0
    if check_in and check_out:
        occupied = await db.fetch(
            f"""
            SELECT DISTINCT room_id FROM "{schema}".hotel_reservations
            WHERE status IN ('confirmed', 'checked_in')
              AND check_in_date < $1
              AND check_out_date > $2
            """,
            check_out, check_in
        )
        occupied_ids = [r["room_id"] for r in occupied]
        count_row = await db.fetchval(
            f"""
            SELECT COUNT(*) FROM "{schema}".rooms
            WHERE room_type_id = $1
              AND status NOT IN ('maintenance', 'cleaning')
              AND id != ALL($2::uuid[])
            """,
            room_type_id,
            occupied_ids
        )
        available_count = count_row or 0
    else:
        count_row = await db.fetchval(
            f"""
            SELECT COUNT(*) FROM "{schema}".rooms
            WHERE room_type_id = $1 AND status = 'available'
            """,
            room_type_id
        )
        available_count = count_row or 0

    return {
        "room_type_id": rt["id"],
        "name": rt["name"],
        "description": rt["description"],
        "base_price": rt["base_price"],
        "max_adults": rt["max_adults"],
        "max_children": rt["max_children"],
        "bed_type": rt["bed_type"],
        "floor_area_sqm": rt["floor_area_sqm"],
        "view_type": rt["view_type"],
        "amenities": rt["amenities"],
        "image_urls": rt["image_urls"],
        "available_from": check_in,
        "available_to": check_out,
        "available_count": available_count,
    }