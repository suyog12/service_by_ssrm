from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class RoomCreate(BaseModel):
    name: Optional[str] = None
    type: str = Field(default="group", pattern="^(group|announcement)$")


class RoomUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)


class DirectRoomCreate(BaseModel):
    user_id: UUID


class MemberAdd(BaseModel):
    user_id: UUID


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    file_url: Optional[str] = None
    reply_to_id: Optional[UUID] = None


class MessageEdit(BaseModel):
    content: str = Field(..., min_length=1)


class ReactionAdd(BaseModel):
    emoji: str = Field(..., min_length=1, max_length=10)


class BroadcastCreate(BaseModel):
    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    role_template_id: Optional[UUID] = None


class UploadUrlRequest(BaseModel):
    room_id: UUID
    filename: str = Field(..., min_length=1)