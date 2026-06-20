import asyncpg
from uuid import UUID
from typing import Optional
from fastapi import HTTPException

from app.schemas.housekeeping import (
    HousekeepingTaskCreate,
    HousekeepingTaskUpdate,
    HousekeepingKitItemCreate,
    MinibarItemCreate,
)


VALID_TASK_TYPES = {"cleaning", "turndown", "inspection", "maintenance"}
VALID_STATUSES = {"pending", "in_progress", "done", "verified"}


# Housekeeping Tasks 

async def create_task(
    data: HousekeepingTaskCreate,
    schema: str,
    db: asyncpg.Connection,
    created_by: UUID
):
    if data.task_type not in VALID_TASK_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid task_type. Must be one of: {', '.join(VALID_TASK_TYPES)}"
        )

    room = await db.fetchrow(
        f'SELECT id FROM "{schema}".rooms WHERE id = $1',
        data.room_id
    )
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".housekeeping_tasks
            (room_id, assigned_to, assigned_by, task_type, status, notes)
        VALUES ($1, $2, $3, $4, 'pending', $5)
        RETURNING *
        """,
        data.room_id,
        data.assigned_to,
        created_by,
        data.task_type,
        data.notes,
    )

    if data.task_type == "cleaning":
        await db.execute(
            f'UPDATE "{schema}".rooms SET status = $1, updated_at = NOW() WHERE id = $2',
            "cleaning",
            data.room_id
        )

    return dict(row)


async def list_tasks(
    schema: str,
    db: asyncpg.Connection,
    room_id: Optional[UUID] = None,
    status: Optional[str] = None,
    assigned_to: Optional[UUID] = None
):
    conditions = []
    params = []
    idx = 1

    if room_id:
        conditions.append(f"room_id = ${idx}")
        params.append(room_id)
        idx += 1
    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if assigned_to:
        conditions.append(f"assigned_to = ${idx}")
        params.append(assigned_to)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await db.fetch(
        f'SELECT * FROM "{schema}".housekeeping_tasks {where} ORDER BY created_at DESC',
        *params
    )
    return [dict(r) for r in rows]


async def get_task(task_id: UUID, schema: str, db: asyncpg.Connection):
    row = await db.fetchrow(
        f'SELECT * FROM "{schema}".housekeeping_tasks WHERE id = $1',
        task_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Housekeeping task not found")
    return dict(row)


async def update_task(
    task_id: UUID,
    data: HousekeepingTaskUpdate,
    schema: str,
    db: asyncpg.Connection,
    current_user_id: UUID
):
    existing = await get_task(task_id, schema, db)

    if data.task_type and data.task_type not in VALID_TASK_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid task_type. Must be one of: {', '.join(VALID_TASK_TYPES)}"
        )
    if data.status and data.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"
        )

    updates = {}
    if data.task_type is not None:
        updates["task_type"] = data.task_type
    if data.assigned_to is not None:
        updates["assigned_to"] = data.assigned_to
    if data.notes is not None:
        updates["notes"] = data.notes
    if data.status is not None:
        updates["status"] = data.status
        if data.status == "in_progress" and not existing.get("started_at"):
            updates["started_at"] = "NOW()"
        elif data.status == "done" and not existing.get("completed_at"):
            updates["completed_at"] = "NOW()"
        elif data.status == "verified":
            updates["verified_at"] = "NOW()"
            updates["verified_by"] = str(current_user_id)

    if not updates:
        return existing

    set_parts = []
    set_params = []
    param_idx = 1
    for key, val in updates.items():
        if val == "NOW()":
            set_parts.append(f"{key} = NOW()")
        elif key == "verified_by":
            set_parts.append(f"{key} = ${param_idx}::uuid")
            set_params.append(val)
            param_idx += 1
        else:
            set_parts.append(f"{key} = ${param_idx}")
            set_params.append(val)
            param_idx += 1

    set_parts.append("updated_at = NOW()")
    set_params.append(task_id)

    row = await db.fetchrow(
        f'UPDATE "{schema}".housekeeping_tasks SET {", ".join(set_parts)} WHERE id = ${param_idx} RETURNING *',
        *set_params
    )

    if data.status in ("done", "verified"):
        await db.execute(
            f'UPDATE "{schema}".rooms SET status = $1, updated_at = NOW() WHERE id = $2',
            "available",
            existing["room_id"]
        )

    return dict(row)


async def delete_task(task_id: UUID, schema: str, db: asyncpg.Connection):
    existing = await get_task(task_id, schema, db)
    if existing["status"] != "pending":
        raise HTTPException(status_code=400, detail="Only pending tasks can be deleted")
    await db.execute(
        f'DELETE FROM "{schema}".housekeeping_tasks WHERE id = $1',
        task_id
    )
    return {"detail": "Task deleted"}


# Housekeeping Kit 

async def list_kit_items(room_type_id: UUID, schema: str, db: asyncpg.Connection):
    room_type = await db.fetchrow(
        f'SELECT id FROM "{schema}".room_types WHERE id = $1',
        room_type_id
    )
    if not room_type:
        raise HTTPException(status_code=404, detail="Room type not found")
    rows = await db.fetch(
        f'SELECT * FROM "{schema}".room_type_housekeeping_kit WHERE room_type_id = $1',
        room_type_id
    )
    return [dict(r) for r in rows]


async def upsert_kit_item(
    room_type_id: UUID,
    data: HousekeepingKitItemCreate,
    schema: str,
    db: asyncpg.Connection
):
    room_type = await db.fetchrow(
        f'SELECT id FROM "{schema}".room_types WHERE id = $1',
        room_type_id
    )
    if not room_type:
        raise HTTPException(status_code=404, detail="Room type not found")

    ingredient = await db.fetchrow(
        f'SELECT id FROM "{schema}".ingredients WHERE id = $1',
        data.ingredient_id
    )
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".room_type_housekeeping_kit
            (room_type_id, ingredient_id, quantity_per_turn)
        VALUES ($1, $2, $3)
        ON CONFLICT (room_type_id, ingredient_id)
        DO UPDATE SET quantity_per_turn = EXCLUDED.quantity_per_turn
        RETURNING *
        """,
        room_type_id,
        data.ingredient_id,
        data.quantity_per_turn,
    )
    return dict(row)


async def delete_kit_item(
    room_type_id: UUID,
    ingredient_id: UUID,
    schema: str,
    db: asyncpg.Connection
):
    result = await db.execute(
        f'DELETE FROM "{schema}".room_type_housekeeping_kit WHERE room_type_id = $1 AND ingredient_id = $2',
        room_type_id,
        ingredient_id
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Kit item not found")
    return {"detail": "Kit item removed"}


# Minibar 

async def list_minibar_items(room_type_id: UUID, schema: str, db: asyncpg.Connection):
    room_type = await db.fetchrow(
        f'SELECT id FROM "{schema}".room_types WHERE id = $1',
        room_type_id
    )
    if not room_type:
        raise HTTPException(status_code=404, detail="Room type not found")
    rows = await db.fetch(
        f'SELECT * FROM "{schema}".room_type_minibar WHERE room_type_id = $1',
        room_type_id
    )
    return [dict(r) for r in rows]


async def upsert_minibar_item(
    room_type_id: UUID,
    data: MinibarItemCreate,
    schema: str,
    db: asyncpg.Connection
):
    room_type = await db.fetchrow(
        f'SELECT id FROM "{schema}".room_types WHERE id = $1',
        room_type_id
    )
    if not room_type:
        raise HTTPException(status_code=404, detail="Room type not found")

    ingredient = await db.fetchrow(
        f'SELECT id FROM "{schema}".ingredients WHERE id = $1',
        data.ingredient_id
    )
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".room_type_minibar
            (room_type_id, ingredient_id, quantity)
        VALUES ($1, $2, $3)
        ON CONFLICT (room_type_id, ingredient_id)
        DO UPDATE SET quantity = EXCLUDED.quantity
        RETURNING *
        """,
        room_type_id,
        data.ingredient_id,
        data.quantity,
    )
    return dict(row)


async def delete_minibar_item(
    room_type_id: UUID,
    ingredient_id: UUID,
    schema: str,
    db: asyncpg.Connection
):
    result = await db.execute(
        f'DELETE FROM "{schema}".room_type_minibar WHERE room_type_id = $1 AND ingredient_id = $2',
        room_type_id,
        ingredient_id
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Minibar item not found")
    return {"detail": "Minibar item removed"}