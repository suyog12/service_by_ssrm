from uuid import UUID
from fastapi import HTTPException
from app.core.encryption import encrypt, decrypt
import re


# Helpers 

def _decrypt_message(row: dict) -> dict:
    d = dict(row)
    if d.get("content") and not d.get("is_deleted"):
        d["content"] = decrypt(d["content"])
    elif d.get("is_deleted"):
        d["content"] = "This message was deleted"
    return d


def _extract_mentions(content: str) -> list[str]:
    return re.findall(r"@(\w+)", content)


async def _get_users_by_feature(db, schema: str, feature_code: str) -> list:
    rows = await db.fetch(
        f"""
        SELECT DISTINCT up.id
        FROM "{schema}".user_profiles up
        JOIN "{schema}".role_permissions rp ON rp.role_template_id = up.role_template_id
        WHERE rp.feature_code = $1 AND rp.access_level != 'none'
        UNION
        SELECT up.id FROM "{schema}".user_profiles up WHERE up.is_admin = TRUE
        """,
        feature_code
    )
    return [r["id"] for r in rows]


async def _fire_notification(db, schema: str, user_id, event_code: str,
                              title: str, body: str, ref_type: str = None,
                              ref_id=None):
    await db.execute(
        f"""
        INSERT INTO "{schema}".notifications
            (user_id, event_code, title, body, reference_type, reference_id)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        user_id, event_code, title, body, ref_type, ref_id
    )


async def _update_last_seen(db, schema: str, user_id: UUID):
    await db.execute(
        f"""
        UPDATE "{schema}".user_profiles
        SET last_seen_at = NOW()
        WHERE id = $1
        """,
        user_id
    )


# Rooms 

async def create_room(db, schema: str, user_id: UUID, data: dict) -> dict:
    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".chat_rooms
            (name, type, created_by, room_admin_id)
        VALUES ($1, $2, $3, $3)
        RETURNING *
        """,
        data.get("name"), data["type"], user_id
    )
    await db.execute(
        f"""
        INSERT INTO "{schema}".chat_members (room_id, user_id)
        VALUES ($1, $2) ON CONFLICT DO NOTHING
        """,
        row["id"], user_id
    )
    return dict(row)


async def get_or_create_direct_room(
    db, schema: str, user_a: UUID, user_b: UUID
) -> dict:
    # Check if user_b exists
    exists = await db.fetchval(
        f'SELECT id FROM "{schema}".user_profiles WHERE id = $1', user_b
    )
    if not exists:
        raise HTTPException(404, "User not found")

    # Find existing direct room between these two users
    row = await db.fetchrow(
        f"""
        SELECT cr.* FROM "{schema}".chat_rooms cr
        JOIN "{schema}".chat_members cm1 ON cm1.room_id = cr.id AND cm1.user_id = $1
        JOIN "{schema}".chat_members cm2 ON cm2.room_id = cr.id AND cm2.user_id = $2
        WHERE cr.type = 'direct'
        LIMIT 1
        """,
        user_a, user_b
    )
    if row:
        return dict(row)

    # Create new direct room
    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".chat_rooms (type, created_by, room_admin_id)
        VALUES ('direct', $1, $1)
        RETURNING *
        """,
        user_a
    )
    for uid in [user_a, user_b]:
        await db.execute(
            f"""
            INSERT INTO "{schema}".chat_members (room_id, user_id)
            VALUES ($1, $2) ON CONFLICT DO NOTHING
            """,
            row["id"], uid
        )
    return dict(row)


async def list_rooms(db, schema: str, user_id: UUID) -> list[dict]:
    rows = await db.fetch(
        f"""
        SELECT cr.*, 
               (SELECT COUNT(*) FROM "{schema}".messages m
                WHERE m.room_id = cr.id AND m.is_read = FALSE
                AND m.sender_id != $1 AND m.is_deleted = FALSE) AS unread_count
        FROM "{schema}".chat_rooms cr
        JOIN "{schema}".chat_members cm ON cm.room_id = cr.id
        WHERE cm.user_id = $1 AND cr.is_archived = FALSE
        ORDER BY cr.updated_at DESC
        """,
        user_id
    )
    return [dict(r) for r in rows]


async def get_room(db, schema: str, room_id: UUID, user_id: UUID) -> dict:
    row = await db.fetchrow(
        f"""
        SELECT cr.* FROM "{schema}".chat_rooms cr
        JOIN "{schema}".chat_members cm ON cm.room_id = cr.id
        WHERE cr.id = $1 AND cm.user_id = $2
        """,
        room_id, user_id
    )
    if not row:
        raise HTTPException(404, "Room not found or you are not a member")
    members = await db.fetch(
        f"""
        SELECT cm.user_id, up.display_name, up.last_seen_at
        FROM "{schema}".chat_members cm
        JOIN "{schema}".user_profiles up ON up.id = cm.user_id
        WHERE cm.room_id = $1
        """,
        room_id
    )
    result = dict(row)
    result["members"] = [dict(m) for m in members]
    return result


async def update_room(
    db, schema: str, room_id: UUID, user_id: UUID, data: dict
) -> dict:
    room = await db.fetchrow(
        f'SELECT * FROM "{schema}".chat_rooms WHERE id = $1', room_id
    )
    if not room:
        raise HTTPException(404, "Room not found")
    if str(room["room_admin_id"]) != str(user_id):
        raise HTTPException(403, "Only the room admin can update this room")
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".chat_rooms
        SET name = $1, updated_at = NOW()
        WHERE id = $2
        RETURNING *
        """,
        data.get("name"), room_id
    )
    return dict(row)


async def archive_room(
    db, schema: str, room_id: UUID, user_id: UUID
) -> dict:
    room = await db.fetchrow(
        f'SELECT * FROM "{schema}".chat_rooms WHERE id = $1', room_id
    )
    if not room:
        raise HTTPException(404, "Room not found")
    if str(room["room_admin_id"]) != str(user_id):
        raise HTTPException(403, "Only the room admin can archive this room")
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".chat_rooms
        SET is_archived = TRUE, archived_at = NOW(), updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        room_id
    )
    return dict(row)


async def delete_room(
    db, schema: str, room_id: UUID, user_id: UUID, is_admin: bool
) -> None:
    room = await db.fetchrow(
        f'SELECT * FROM "{schema}".chat_rooms WHERE id = $1', room_id
    )
    if not room:
        raise HTTPException(404, "Room not found")
    if not is_admin and str(room["room_admin_id"]) != str(user_id):
        raise HTTPException(403, "Only the room admin can delete this room")
    await db.execute(
        f'DELETE FROM "{schema}".chat_rooms WHERE id = $1', room_id
    )


async def add_member(
    db, schema: str, room_id: UUID, user_id: UUID, new_user_id: UUID,
    is_admin: bool
) -> dict:
    room = await db.fetchrow(
        f'SELECT * FROM "{schema}".chat_rooms WHERE id = $1', room_id
    )
    if not room:
        raise HTTPException(404, "Room not found")
    if room["type"] == "direct":
        raise HTTPException(400, "Cannot add members to a direct room")
    if not is_admin and str(room["room_admin_id"]) != str(user_id):
        raise HTTPException(403, "Only the room admin can add members")
    exists = await db.fetchval(
        f'SELECT id FROM "{schema}".user_profiles WHERE id = $1', new_user_id
    )
    if not exists:
        raise HTTPException(404, "User not found")
    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".chat_members (room_id, user_id)
        VALUES ($1, $2)
        ON CONFLICT (room_id, user_id) DO NOTHING
        RETURNING *
        """,
        room_id, new_user_id
    )
    return dict(row) if row else {"room_id": str(room_id), "user_id": str(new_user_id)}


async def remove_member(
    db, schema: str, room_id: UUID, user_id: UUID,
    target_user_id: UUID, is_admin: bool
) -> None:
    room = await db.fetchrow(
        f'SELECT * FROM "{schema}".chat_rooms WHERE id = $1', room_id
    )
    if not room:
        raise HTTPException(404, "Room not found")
    if room["type"] == "direct":
        raise HTTPException(400, "Cannot remove members from a direct room")
    if not is_admin and str(room["room_admin_id"]) != str(user_id):
        raise HTTPException(403, "Only the room admin can remove members")
    await db.execute(
        f"""
        DELETE FROM "{schema}".chat_members
        WHERE room_id = $1 AND user_id = $2
        """,
        room_id, target_user_id
    )


# Messages 

async def send_message(
    db, schema: str, room_id: UUID, sender_id: UUID, data: dict
) -> dict:
    # Verify sender is a member
    member = await db.fetchval(
        f"""
        SELECT id FROM "{schema}".chat_members
        WHERE room_id = $1 AND user_id = $2
        """,
        room_id, sender_id
    )
    if not member:
        raise HTTPException(403, "You are not a member of this room")

    room = await db.fetchrow(
        f'SELECT * FROM "{schema}".chat_rooms WHERE id = $1', room_id
    )
    if not room:
        raise HTTPException(404, "Room not found")

    # Announcement rooms — only users with comms.announcements can post
    if room["type"] == "announcement":
        has_perm = await db.fetchval(
            f"""
            SELECT COUNT(*) FROM "{schema}".role_permissions rp
            JOIN "{schema}".user_profiles up ON up.role_template_id = rp.role_template_id
            WHERE up.id = $1 AND rp.feature_code = 'comms.announcements'
            AND rp.access_level != 'none'
            """,
            sender_id
        )
        is_admin = await db.fetchval(
            f'SELECT is_admin FROM "{schema}".user_profiles WHERE id = $1',
            sender_id
        )
        if not has_perm and not is_admin:
            raise HTTPException(
                403, "Only users with announcement permission can post here"
            )

    encrypted_content = encrypt(data["content"])
    file_url = encrypt(data["file_url"]) if data.get("file_url") else None

    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".messages
            (room_id, sender_id, content, file_url, reply_to_id)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        room_id, sender_id, encrypted_content, file_url,
        data.get("reply_to_id")
    )

    # Update room updated_at
    await db.execute(
        f'UPDATE "{schema}".chat_rooms SET updated_at = NOW() WHERE id = $1',
        room_id
    )

    # Handle @mentions
    mentions = _extract_mentions(data["content"])
    if mentions:
        for username in mentions:
            user = await db.fetchrow(
                f"""
                SELECT up.id FROM "{schema}".user_profiles up
                JOIN core.users cu ON cu.id = up.id
                WHERE cu.full_name ILIKE $1
                LIMIT 1
                """,
                f"%{username}%"
            )
            if user and str(user["id"]) != str(sender_id):
                await db.execute(
                    f"""
                    INSERT INTO "{schema}".message_mentions (message_id, user_id)
                    VALUES ($1, $2) ON CONFLICT DO NOTHING
                    """,
                    row["id"], user["id"]
                )
                await _fire_notification(
                    db, schema, user["id"],
                    "comms.mention",
                    "You were mentioned",
                    f"Someone mentioned you in a message",
                    "message", row["id"]
                )

    # Notify room members
    members = await db.fetch(
        f"""
        SELECT user_id FROM "{schema}".chat_members
        WHERE room_id = $1 AND user_id != $2
        """,
        room_id, sender_id
    )
    for m in members:
        await _fire_notification(
            db, schema, m["user_id"],
            "comms.message",
            "New message",
            "You have a new message",
            "message", row["id"]
        )

    result = _decrypt_message(dict(row))
    return result


async def list_messages(
    db, schema: str, room_id: UUID, user_id: UUID,
    before_id: UUID = None, limit: int = 25
) -> list[dict]:
    member = await db.fetchval(
        f"""
        SELECT id FROM "{schema}".chat_members
        WHERE room_id = $1 AND user_id = $2
        """,
        room_id, user_id
    )
    if not member:
        raise HTTPException(403, "You are not a member of this room")

    if before_id:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".messages
            WHERE room_id = $1
            AND id < $2
            ORDER BY created_at ASC
            LIMIT $3
            """,
            room_id, before_id, limit
        )
    else:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".messages
            WHERE room_id = $1
            ORDER BY created_at ASC
            LIMIT $2
            """,
            room_id, limit
        )
    return [_decrypt_message(dict(r)) for r in rows]


async def mark_messages_read(
    db, schema: str, room_id: UUID, user_id: UUID
) -> dict:
    await db.execute(
        f"""
        UPDATE "{schema}".messages
        SET is_read = TRUE
        WHERE room_id = $1 AND sender_id != $2 AND is_read = FALSE
        """,
        room_id, user_id
    )
    # Auto-mark related notifications as read
    await db.execute(
        f"""
        UPDATE "{schema}".notifications
        SET is_read = TRUE
        WHERE user_id = $1
        AND event_code IN ('comms.message', 'comms.mention')
        AND reference_id IN (
            SELECT id FROM "{schema}".messages WHERE room_id = $2
        )
        """,
        user_id, room_id
    )

    # Insert read receipts for unread messages
    unread = await db.fetch(
        f"""
        SELECT id FROM "{schema}".messages
        WHERE room_id = $1 AND sender_id != $2
        """,
        room_id, user_id
    )
    for msg in unread:
        await db.execute(
            f"""
            INSERT INTO "{schema}".message_read_receipts (message_id, user_id)
            VALUES ($1, $2) ON CONFLICT DO NOTHING
            """,
            msg["id"], user_id
        )
    return {"status": "ok"}


async def edit_message(
    db, schema: str, message_id: UUID, user_id: UUID, new_content: str
) -> dict:
    msg = await db.fetchrow(
        f'SELECT * FROM "{schema}".messages WHERE id = $1', message_id
    )
    if not msg:
        raise HTTPException(404, "Message not found")
    if str(msg["sender_id"]) != str(user_id):
        raise HTTPException(403, "You can only edit your own messages")
    if msg["is_deleted"]:
        raise HTTPException(400, "Cannot edit a deleted message")

    # Save edit history
    await db.execute(
        f"""
        INSERT INTO "{schema}".message_edits (message_id, old_content)
        VALUES ($1, $2)
        """,
        message_id, msg["content"]
    )

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".messages
        SET content = $1, is_edited = TRUE, edited_at = NOW()
        WHERE id = $2
        RETURNING *
        """,
        encrypt(new_content), message_id
    )
    return _decrypt_message(dict(row))


async def delete_message(
    db, schema: str, message_id: UUID, user_id: UUID, is_admin: bool
) -> dict:
    msg = await db.fetchrow(
        f'SELECT * FROM "{schema}".messages WHERE id = $1', message_id
    )
    if not msg:
        raise HTTPException(404, "Message not found")
    if not is_admin and str(msg["sender_id"]) != str(user_id):
        raise HTTPException(403, "You can only delete your own messages")

    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".messages
        SET is_deleted = TRUE, deleted_at = NOW(), content = ''
        WHERE id = $1
        RETURNING *
        """,
        message_id
    )
    result = dict(row)
    result["content"] = "This message was deleted"
    return result


async def add_reaction(
    db, schema: str, message_id: UUID, user_id: UUID, emoji: str
) -> dict:
    msg = await db.fetchval(
        f'SELECT id FROM "{schema}".messages WHERE id = $1', message_id
    )
    if not msg:
        raise HTTPException(404, "Message not found")
    row = await db.fetchrow(
        f"""
        INSERT INTO "{schema}".message_reactions (message_id, user_id, emoji)
        VALUES ($1, $2, $3)
        ON CONFLICT (message_id, user_id, emoji) DO NOTHING
        RETURNING *
        """,
        message_id, user_id, emoji
    )
    return dict(row) if row else {"message_id": str(message_id), "emoji": emoji}


async def remove_reaction(
    db, schema: str, message_id: UUID, user_id: UUID, emoji: str
) -> None:
    await db.execute(
        f"""
        DELETE FROM "{schema}".message_reactions
        WHERE message_id = $1 AND user_id = $2 AND emoji = $3
        """,
        message_id, user_id, emoji
    )


async def get_message_edit_history(
    db, schema: str, message_id: UUID
) -> list[dict]:
    rows = await db.fetch(
        f"""
        SELECT * FROM "{schema}".message_edits
        WHERE message_id = $1
        ORDER BY edited_at ASC
        """,
        message_id
    )
    result = []
    for r in rows:
        d = dict(r)
        d["old_content"] = decrypt(d["old_content"])
        result.append(d)
    return result


async def search_messages(
    db, schema: str, user_id: UUID, query: str
) -> list[dict]:
    # Get all rooms user is a member of
    room_ids = await db.fetch(
        f"""
        SELECT room_id FROM "{schema}".chat_members WHERE user_id = $1
        """,
        user_id
    )
    if not room_ids:
        return []
    results = []
    for r in room_ids:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".messages
            WHERE room_id = $1 AND is_deleted = FALSE
            ORDER BY created_at DESC
            LIMIT 50
            """,
            r["room_id"]
        )
        for row in rows:
            decrypted = _decrypt_message(dict(row))
            if query.lower() in decrypted.get("content", "").lower():
                results.append(decrypted)
    return results


async def get_unread_count(
    db, schema: str, user_id: UUID
) -> dict:
    total = await db.fetchval(
        f"""
        SELECT COUNT(*) FROM "{schema}".messages m
        JOIN "{schema}".chat_members cm ON cm.room_id = m.room_id
        WHERE cm.user_id = $1
        AND m.sender_id != $1
        AND m.is_read = FALSE
        AND m.is_deleted = FALSE
        """,
        user_id
    )
    rows = await db.fetch(
        f"""
        SELECT m.room_id,
               COUNT(*) AS unread
        FROM "{schema}".messages m
        JOIN "{schema}".chat_members cm ON cm.room_id = m.room_id
        WHERE cm.user_id = $1
        AND m.sender_id != $1
        AND m.is_read = FALSE
        AND m.is_deleted = FALSE
        GROUP BY m.room_id
        """,
        user_id
    )
    return {
        "total_unread": total,
        "per_room": {str(r["room_id"]): r["unread"] for r in rows}
    }


# Notifications 

async def list_notifications(
    db, schema: str, user_id: UUID, unread_only: bool = False
) -> list[dict]:
    if unread_only:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".notifications
            WHERE user_id = $1 AND is_read = FALSE
            ORDER BY created_at DESC
            """,
            user_id
        )
    else:
        rows = await db.fetch(
            f"""
            SELECT * FROM "{schema}".notifications
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 100
            """,
            user_id
        )
    return [dict(r) for r in rows]


async def mark_notification_read(
    db, schema: str, notification_id: UUID, user_id: UUID
) -> dict:
    row = await db.fetchrow(
        f"""
        UPDATE "{schema}".notifications
        SET is_read = TRUE
        WHERE id = $1 AND user_id = $2
        RETURNING *
        """,
        notification_id, user_id
    )
    if not row:
        raise HTTPException(404, "Notification not found")
    return dict(row)


async def mark_all_notifications_read(
    db, schema: str, user_id: UUID
) -> dict:
    await db.execute(
        f"""
        UPDATE "{schema}".notifications
        SET is_read = TRUE
        WHERE user_id = $1 AND is_read = FALSE
        """,
        user_id
    )
    return {"status": "ok"}


async def get_unread_notification_count(
    db, schema: str, user_id: UUID
) -> dict:
    count = await db.fetchval(
        f"""
        SELECT COUNT(*) FROM "{schema}".notifications
        WHERE user_id = $1 AND is_read = FALSE
        """,
        user_id
    )
    return {"unread_count": count}


async def send_broadcast(
    db, schema: str, sender_id: UUID, data: dict
) -> dict:
    if data.get("role_template_id"):
        recipients = await db.fetch(
            f"""
            SELECT id FROM "{schema}".user_profiles
            WHERE role_template_id = $1
            """,
            data["role_template_id"]
        )
    else:
        recipients = await db.fetch(
            f'SELECT id FROM "{schema}".user_profiles'
        )
    count = 0
    for r in recipients:
        if str(r["id"]) == str(sender_id):
            continue
        await _fire_notification(
            db, schema, r["id"],
            "broadcast",
            data["title"],
            data["body"],
        )
        count += 1
    return {"sent_to": count}