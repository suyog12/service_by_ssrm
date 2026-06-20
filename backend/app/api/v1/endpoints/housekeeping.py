from fastapi import APIRouter, Depends, Query
from typing import Optional
from uuid import UUID

from app.core.dependencies import require_feature, get_db
from app.schemas.housekeeping import (
    HousekeepingTaskCreate,
    HousekeepingTaskUpdate,
    HousekeepingKitItemCreate,
    MinibarItemCreate,
)
from app.services import housekeeping_service

router = APIRouter(prefix="/housekeeping", tags=["housekeeping"])


# Tasks 

@router.post("/tasks", status_code=201)
async def create_task(
    data: HousekeepingTaskCreate,
    current_user=Depends(require_feature("hotel.housekeeping", "edit")),
    db=Depends(get_db)
):
    return await housekeeping_service.create_task(
        data, current_user["schema_name"], db, current_user["user_id"]
    )


@router.get("/tasks")
async def list_tasks(
    room_id: Optional[UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    assigned_to: Optional[UUID] = Query(default=None),
    current_user=Depends(require_feature("hotel.housekeeping", "view")),
    db=Depends(get_db)
):
    return await housekeeping_service.list_tasks(
        current_user["schema_name"], db, room_id, status, assigned_to
    )


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: UUID,
    current_user=Depends(require_feature("hotel.housekeeping", "view")),
    db=Depends(get_db)
):
    return await housekeeping_service.get_task(
        task_id, current_user["schema_name"], db
    )


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: UUID,
    data: HousekeepingTaskUpdate,
    current_user=Depends(require_feature("hotel.housekeeping", "edit")),
    db=Depends(get_db)
):
    return await housekeeping_service.update_task(
        task_id, data, current_user["schema_name"], db, current_user["user_id"]
    )


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: UUID,
    current_user=Depends(require_feature("hotel.housekeeping", "edit")),
    db=Depends(get_db)
):
    return await housekeeping_service.delete_task(
        task_id, current_user["schema_name"], db
    )


# Housekeeping Kit 

@router.get("/room-types/{room_type_id}/kit")
async def list_kit_items(
    room_type_id: UUID,
    current_user=Depends(require_feature("hotel.housekeeping", "view")),
    db=Depends(get_db)
):
    return await housekeeping_service.list_kit_items(
        room_type_id, current_user["schema_name"], db
    )


@router.put("/room-types/{room_type_id}/kit", status_code=201)
async def upsert_kit_item(
    room_type_id: UUID,
    data: HousekeepingKitItemCreate,
    current_user=Depends(require_feature("hotel.housekeeping", "edit")),
    db=Depends(get_db)
):
    return await housekeeping_service.upsert_kit_item(
        room_type_id, data, current_user["schema_name"], db
    )


@router.delete("/room-types/{room_type_id}/kit/{ingredient_id}")
async def delete_kit_item(
    room_type_id: UUID,
    ingredient_id: UUID,
    current_user=Depends(require_feature("hotel.housekeeping", "edit")),
    db=Depends(get_db)
):
    return await housekeeping_service.delete_kit_item(
        room_type_id, ingredient_id, current_user["schema_name"], db
    )


# Minibar 

@router.get("/room-types/{room_type_id}/minibar")
async def list_minibar_items(
    room_type_id: UUID,
    current_user=Depends(require_feature("hotel.housekeeping", "view")),
    db=Depends(get_db)
):
    return await housekeeping_service.list_minibar_items(
        room_type_id, current_user["schema_name"], db
    )


@router.put("/room-types/{room_type_id}/minibar", status_code=201)
async def upsert_minibar_item(
    room_type_id: UUID,
    data: MinibarItemCreate,
    current_user=Depends(require_feature("hotel.housekeeping", "edit")),
    db=Depends(get_db)
):
    return await housekeeping_service.upsert_minibar_item(
        room_type_id, data, current_user["schema_name"], db
    )


@router.delete("/room-types/{room_type_id}/minibar/{ingredient_id}")
async def delete_minibar_item(
    room_type_id: UUID,
    ingredient_id: UUID,
    current_user=Depends(require_feature("hotel.housekeeping", "edit")),
    db=Depends(get_db)
):
    return await housekeeping_service.delete_minibar_item(
        room_type_id, ingredient_id, current_user["schema_name"], db
    )