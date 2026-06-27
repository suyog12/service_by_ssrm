from fastapi import APIRouter, Depends, Query
from uuid import UUID
from typing import Optional

from app.core.dependencies import require_feature
from app.core.database import get_tenant_db
from app.core import r2 as r2_service
from app.schemas.comms import (
    RoomCreate, RoomUpdate, DirectRoomCreate, MemberAdd,
    MessageCreate, MessageEdit, ReactionAdd,
    BroadcastCreate, UploadUrlRequest,
)
from app.services import comms_service

router = APIRouter(tags=["Comms"])


# Upload URL 

@router.post("/comms/upload-url")
async def get_upload_url(
    body: UploadUrlRequest,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    return r2_service.generate_upload_url(
        schema, str(body.room_id), body.filename
    )


# Rooms 

@router.post("/comms/rooms", status_code=201)
async def create_room(
    body: RoomCreate,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.create_room(
            db, schema, current_user["user_id"], body.model_dump()
        )


@router.post("/comms/rooms/direct", status_code=201)
async def get_or_create_direct_room(
    body: DirectRoomCreate,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.get_or_create_direct_room(
            db, schema, current_user["user_id"], body.user_id
        )


@router.get("/comms/rooms")
async def list_rooms(
    current_user: dict = Depends(require_feature("comms.chat", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.list_rooms(
            db, schema, current_user["user_id"]
        )


@router.get("/comms/rooms/unread")
async def get_unread_count(
    current_user: dict = Depends(require_feature("comms.chat", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.get_unread_count(
            db, schema, current_user["user_id"]
        )


@router.get("/comms/rooms/search")
async def search_messages(
    q: str = Query(..., min_length=1),
    current_user: dict = Depends(require_feature("comms.chat", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.search_messages(
            db, schema, current_user["user_id"], q
        )


@router.get("/comms/rooms/{room_id}")
async def get_room(
    room_id: UUID,
    current_user: dict = Depends(require_feature("comms.chat", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.get_room(
            db, schema, room_id, current_user["user_id"]
        )


@router.patch("/comms/rooms/{room_id}")
async def update_room(
    room_id: UUID,
    body: RoomUpdate,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.update_room(
            db, schema, room_id, current_user["user_id"], body.model_dump()
        )


@router.post("/comms/rooms/{room_id}/archive")
async def archive_room(
    room_id: UUID,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.archive_room(
            db, schema, room_id, current_user["user_id"]
        )


@router.delete("/comms/rooms/{room_id}", status_code=204)
async def delete_room(
    room_id: UUID,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        await comms_service.delete_room(
            db, schema, room_id, current_user["user_id"],
            current_user.get("is_admin", False)
        )


@router.post("/comms/rooms/{room_id}/members", status_code=201)
async def add_member(
    room_id: UUID,
    body: MemberAdd,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.add_member(
            db, schema, room_id, current_user["user_id"], body.user_id,
            current_user.get("is_admin", False)
        )


@router.delete("/comms/rooms/{room_id}/members/{target_user_id}", status_code=204)
async def remove_member(
    room_id: UUID,
    target_user_id: UUID,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        await comms_service.remove_member(
            db, schema, room_id, current_user["user_id"], target_user_id,
            current_user.get("is_admin", False)
        )


# Messages 

@router.post("/comms/rooms/{room_id}/messages", status_code=201)
async def send_message(
    room_id: UUID,
    body: MessageCreate,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.send_message(
            db, schema, room_id, current_user["user_id"], body.model_dump()
        )


@router.get("/comms/rooms/{room_id}/messages")
async def list_messages(
    room_id: UUID,
    before_id: Optional[UUID] = Query(default=None),
    limit: int = Query(default=25, le=50),
    current_user: dict = Depends(require_feature("comms.chat", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.list_messages(
            db, schema, room_id, current_user["user_id"], before_id, limit
        )


@router.post("/comms/rooms/{room_id}/messages/read")
async def mark_messages_read(
    room_id: UUID,
    current_user: dict = Depends(require_feature("comms.chat", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.mark_messages_read(
            db, schema, room_id, current_user["user_id"]
        )


@router.patch("/comms/messages/{message_id}")
async def edit_message(
    message_id: UUID,
    body: MessageEdit,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.edit_message(
            db, schema, message_id, current_user["user_id"], body.content
        )


@router.delete("/comms/messages/{message_id}", status_code=204)
async def delete_message(
    message_id: UUID,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        await comms_service.delete_message(
            db, schema, message_id, current_user["user_id"],
            current_user.get("is_admin", False)
        )


@router.get("/comms/messages/{message_id}/history")
async def get_message_history(
    message_id: UUID,
    current_user: dict = Depends(require_feature("comms.chat", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.get_message_edit_history(
            db, schema, message_id
        )


@router.post("/comms/messages/{message_id}/reactions", status_code=201)
async def add_reaction(
    message_id: UUID,
    body: ReactionAdd,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.add_reaction(
            db, schema, message_id, current_user["user_id"], body.emoji
        )


@router.delete("/comms/messages/{message_id}/reactions/{emoji}", status_code=204)
async def remove_reaction(
    message_id: UUID,
    emoji: str,
    current_user: dict = Depends(require_feature("comms.chat", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        await comms_service.remove_reaction(
            db, schema, message_id, current_user["user_id"], emoji
        )


# Notifications 

@router.get("/comms/notifications")
async def list_notifications(
    unread_only: bool = Query(default=False),
    current_user: dict = Depends(require_feature("comms.chat", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.list_notifications(
            db, schema, current_user["user_id"], unread_only
        )


@router.get("/comms/notifications/count")
async def get_notification_count(
    current_user: dict = Depends(require_feature("comms.chat", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.get_unread_notification_count(
            db, schema, current_user["user_id"]
        )


@router.post("/comms/notifications/read-all")
async def mark_all_read(
    current_user: dict = Depends(require_feature("comms.chat", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.mark_all_notifications_read(
            db, schema, current_user["user_id"]
        )


@router.post("/comms/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: dict = Depends(require_feature("comms.chat", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.mark_notification_read(
            db, schema, notification_id, current_user["user_id"]
        )


# Broadcast 

@router.post("/comms/broadcast", status_code=201)
async def send_broadcast(
    body: BroadcastCreate,
    current_user: dict = Depends(require_feature("comms.announcements", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await comms_service.send_broadcast(
            db, schema, current_user["user_id"], body.model_dump()
        )