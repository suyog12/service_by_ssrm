from uuid import UUID
from fastapi import HTTPException


# Sections 

async def create_section(
    db, schema: str, outlet_id: UUID, data: dict
) -> dict:
    existing = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".sections
        WHERE name = $1 AND outlet_id = $2
        """,
        data["name"], outlet_id
    )
    if existing:
        raise HTTPException(
            400, f"A section named '{data['name']}' already exists"
        )

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".sections (outlet_id, name)
        VALUES ($1, $2)
        RETURNING id, name, is_active
        """,
        outlet_id, data["name"]
    )
    return dict(row)


async def list_sections(
    db, schema: str, outlet_id: UUID
) -> list[dict]:
    rows = await db.fetch(
        f"""
        SELECT id, name, is_active
        FROM "{schema}".sections
        WHERE outlet_id = $1
        ORDER BY name
        """,
        outlet_id
    )
    return [dict(r) for r in rows]


async def update_section(
    db, schema: str, outlet_id: UUID,
    section_id: UUID, data: dict
) -> dict:
    section = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".sections
        WHERE id = $1 AND outlet_id = $2
        """,
        section_id, outlet_id
    )
    if not section:
        raise HTTPException(404, "Section not found")

    if data.get("name"):
        existing = await db.fetchrow(
            f"""
            SELECT id FROM "{schema}".sections
            WHERE name = $1 AND outlet_id = $2 AND id != $3
            """,
            data["name"], outlet_id, section_id
        )
        if existing:
            raise HTTPException(
                400, f"A section named '{data['name']}' already exists"
            )

    fields = []
    values = []
    idx = 1
    for field in ["name", "is_active"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1

    if not fields:
        row = await db.fetchrow(
            f"""
            SELECT id, name, is_active FROM "{schema}".sections
            WHERE id = $1
            """,
            section_id
        )
        return dict(row)

    values.append(section_id)
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".sections
        SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING id, name, is_active
        """,
        *values
    )
    return dict(row)


async def delete_section(
    db, schema: str, outlet_id: UUID, section_id: UUID
) -> None:
    section = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".sections
        WHERE id = $1 AND outlet_id = $2
        """,
        section_id, outlet_id
    )
    if not section:
        raise HTTPException(404, "Section not found")

    tables = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".tables
        WHERE section_id = $1 LIMIT 1
        """,
        section_id
    )
    if tables:
        raise HTTPException(
            400, "Cannot delete section — it has tables assigned to it"
        )

    await db.execute(
        f'DELETE FROM "{schema}".sections WHERE id = $1',
        section_id
    )


# Tables 

async def create_table(
    db, schema: str, outlet_id: UUID, data: dict
) -> dict:
    existing = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".tables
        WHERE table_number = $1 AND outlet_id = $2
        """,
        data["table_number"], outlet_id
    )
    if existing:
        raise HTTPException(
            400,
            f"A table with number '{data['table_number']}' already exists"
        )

    if data.get("section_id"):
        section = await db.fetchrow(
            f"""
            SELECT id FROM "{schema}".sections
            WHERE id = $1 AND outlet_id = $2
            """,
            data["section_id"], outlet_id
        )
        if not section:
            raise HTTPException(400, "Section not found")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".tables
            (outlet_id, table_number, capacity, section_id)
        VALUES ($1, $2, $3, $4)
        RETURNING id, table_number, capacity, status, section_id
        """,
        outlet_id,
        data["table_number"],
        data.get("capacity", 4),
        data.get("section_id"),
    )
    result = dict(row)
    result["section_name"] = await _get_section_name(
        db, schema, result["section_id"]
    )
    return result


async def list_tables(
    db, schema: str, outlet_id: UUID, section_id: UUID = None
) -> list[dict]:
    if section_id:
        rows = await db.fetch(
            f"""
            SELECT t.id, t.table_number, t.capacity, t.status,
                   t.section_id, s.name AS section_name
            FROM "{schema}".tables t
            LEFT JOIN "{schema}".sections s ON s.id = t.section_id
            WHERE t.outlet_id = $1 AND t.section_id = $2
            ORDER BY t.table_number
            """,
            outlet_id, section_id
        )
    else:
        rows = await db.fetch(
            f"""
            SELECT t.id, t.table_number, t.capacity, t.status,
                   t.section_id, s.name AS section_name
            FROM "{schema}".tables t
            LEFT JOIN "{schema}".sections s ON s.id = t.section_id
            WHERE t.outlet_id = $1
            ORDER BY t.table_number
            """,
            outlet_id
        )
    return [dict(r) for r in rows]


async def get_table(
    db, schema: str, outlet_id: UUID, table_id: UUID
) -> dict:
    row = await db.fetchrow(
        f"""
        SELECT t.id, t.table_number, t.capacity, t.status,
               t.section_id, s.name AS section_name
        FROM "{schema}".tables t
        LEFT JOIN "{schema}".sections s ON s.id = t.section_id
        WHERE t.id = $1 AND t.outlet_id = $2
        """,
        table_id, outlet_id
    )
    if not row:
        raise HTTPException(404, "Table not found")
    return dict(row)


async def update_table(
    db, schema: str, outlet_id: UUID,
    table_id: UUID, data: dict
) -> dict:
    table = await db.fetchrow(
        f"""
        SELECT id FROM "{schema}".tables
        WHERE id = $1 AND outlet_id = $2
        """,
        table_id, outlet_id
    )
    if not table:
        raise HTTPException(404, "Table not found")

    if data.get("table_number"):
        existing = await db.fetchrow(
            f"""
            SELECT id FROM "{schema}".tables
            WHERE table_number = $1 AND outlet_id = $2 AND id != $3
            """,
            data["table_number"], outlet_id, table_id
        )
        if existing:
            raise HTTPException(
                400,
                f"A table with number '{data['table_number']}' already exists"
            )

    if data.get("section_id"):
        section = await db.fetchrow(
            f"""
            SELECT id FROM "{schema}".sections
            WHERE id = $1 AND outlet_id = $2
            """,
            data["section_id"], outlet_id
        )
        if not section:
            raise HTTPException(400, "Section not found")

    fields = []
    values = []
    idx = 1
    for field in ["table_number", "capacity", "section_id", "status"]:
        if field in data and data[field] is not None:
            fields.append(f"{field} = ${idx}")
            values.append(data[field])
            idx += 1

    if not fields:
        return await get_table(db, schema, outlet_id, table_id)

    values.append(table_id)
    await db.execute(
        f"""
        UPDATE "{schema}".tables
        SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        """,
        *values
    )
    return await get_table(db, schema, outlet_id, table_id)


async def delete_table(
    db, schema: str, outlet_id: UUID, table_id: UUID
) -> None:
    table = await db.fetchrow(
        f"""
        SELECT id, status FROM "{schema}".tables
        WHERE id = $1 AND outlet_id = $2
        """,
        table_id, outlet_id
    )
    if not table:
        raise HTTPException(404, "Table not found")

    if table["status"] == "occupied":
        raise HTTPException(400, "Cannot delete an occupied table")

    await db.execute(
        f'DELETE FROM "{schema}".tables WHERE id = $1',
        table_id
    )


async def _get_section_name(
    db, schema: str, section_id
) -> str | None:
    if not section_id:
        return None
    row = await db.fetchrow(
        f'SELECT name FROM "{schema}".sections WHERE id = $1',
        section_id
    )
    return row["name"] if row else None