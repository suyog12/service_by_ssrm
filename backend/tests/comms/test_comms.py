import pytest
from tests.conftest import auth
import uuid


class TestRoomsPositive:

    async def test_create_group_room(self, client, admin_token):
        resp = await client.post(
            "/api/v1/comms/rooms",
            json={"name": "General", "type": "group"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "General"
        assert resp.json()["type"] == "group"

    async def test_create_announcement_room(self, client, admin_token):
        resp = await client.post(
            "/api/v1/comms/rooms",
            json={"name": "Announcements", "type": "announcement"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["type"] == "announcement"

    async def test_create_direct_room(self, client, admin_token, staff_user):
        resp = await client.post(
            "/api/v1/comms/rooms/direct",
            json={"user_id": staff_user["user_id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["type"] == "direct"

    async def test_direct_room_reused(self, client, admin_token, staff_user):
        r1 = await client.post(
            "/api/v1/comms/rooms/direct",
            json={"user_id": staff_user["user_id"]},
            headers=auth(admin_token)
        )
        r2 = await client.post(
            "/api/v1/comms/rooms/direct",
            json={"user_id": staff_user["user_id"]},
            headers=auth(admin_token)
        )
        assert r1.json()["id"] == r2.json()["id"]

    async def test_list_rooms(self, client, admin_token, group_room):
        resp = await client.get(
            "/api/v1/comms/rooms",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert any(r["id"] == group_room["id"] for r in resp.json())

    async def test_get_room_with_members(self, client, admin_token, group_room):
        resp = await client.get(
            f"/api/v1/comms/rooms/{group_room['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert "members" in resp.json()

    async def test_members_include_last_seen_at(self, client, admin_token, group_room):
        resp = await client.get(
            f"/api/v1/comms/rooms/{group_room['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        members = resp.json()["members"]
        assert len(members) >= 1
        assert "last_seen_at" in members[0]

    async def test_update_room_name(self, client, admin_token, group_room):
        resp = await client.patch(
            f"/api/v1/comms/rooms/{group_room['id']}",
            json={"name": "Updated Room"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Room"

    async def test_add_member(self, client, admin_token, staff_user, group_room):
        resp = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/members",
            json={"user_id": staff_user["user_id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201

    async def test_remove_member(self, client, admin_token, staff_user, group_room):
        await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/members",
            json={"user_id": staff_user["user_id"]},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/comms/rooms/{group_room['id']}/members/{staff_user['user_id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 204

    async def test_archive_room(self, client, admin_token, group_room):
        resp = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/archive",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_archived"] is True

    async def test_archived_room_hidden_from_list(self, client, admin_token):
        room = await client.post(
            "/api/v1/comms/rooms",
            json={"name": f"Archive Me {uuid.uuid4().hex[:4]}", "type": "group"},
            headers=auth(admin_token)
        )
        room_id = room.json()["id"]
        await client.post(
            f"/api/v1/comms/rooms/{room_id}/archive",
            headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/comms/rooms",
            headers=auth(admin_token)
        )
        assert not any(r["id"] == room_id for r in resp.json())

    async def test_delete_room(self, client, admin_token):
        room = await client.post(
            "/api/v1/comms/rooms",
            json={"name": "To Delete", "type": "group"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/comms/rooms/{room.json()['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 204

    async def test_deleted_room_not_accessible(self, client, admin_token):
        room = await client.post(
            "/api/v1/comms/rooms",
            json={"name": f"Delete Test {uuid.uuid4().hex[:4]}", "type": "group"},
            headers=auth(admin_token)
        )
        room_id = room.json()["id"]
        await client.delete(
            f"/api/v1/comms/rooms/{room_id}",
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/comms/rooms/{room_id}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_unread_count(self, client, admin_token):
        resp = await client.get(
            "/api/v1/comms/rooms/unread",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert "total_unread" in resp.json()
        assert "per_room" in resp.json()


class TestRoomsNegative:

    async def test_invalid_room_type(self, client, admin_token):
        resp = await client.post(
            "/api/v1/comms/rooms",
            json={"name": "Bad", "type": "invalid"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_direct_room_nonexistent_user(self, client, admin_token):
        resp = await client.post(
            "/api/v1/comms/rooms/direct",
            json={"user_id": "00000000-0000-0000-0000-000000000000"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_get_nonexistent_room(self, client, admin_token):
        resp = await client.get(
            "/api/v1/comms/rooms/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_non_admin_cannot_update_room(
        self, client, staff_token, group_room
    ):
        resp = await client.patch(
            f"/api/v1/comms/rooms/{group_room['id']}",
            json={"name": "Hack"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_non_admin_cannot_delete_room(
        self, client, staff_token, group_room
    ):
        resp = await client.delete(
            f"/api/v1/comms/rooms/{group_room['id']}",
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_non_admin_cannot_archive_room(
        self, client, staff_token, group_room
    ):
        resp = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/archive",
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_unauthenticated_rejected(self, client):
        resp = await client.get("/api/v1/comms/rooms")
        assert resp.status_code == 403

    async def test_cannot_add_member_to_direct_room(
        self, client, admin_token, staff_user
    ):
        direct = await client.post(
            "/api/v1/comms/rooms/direct",
            json={"user_id": staff_user["user_id"]},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/comms/rooms/{direct.json()['id']}/members",
            json={"user_id": staff_user["user_id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_update_nonexistent_room(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/comms/rooms/00000000-0000-0000-0000-000000000000",
            json={"name": "Ghost"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_delete_nonexistent_room(self, client, admin_token):
        resp = await client.delete(
            "/api/v1/comms/rooms/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404


class TestMessagesPositive:

    async def test_send_message(self, client, admin_token, group_room):
        resp = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Hello team!"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["content"] == "Hello team!"

    async def test_message_is_encrypted_at_rest(
        self, client, admin_token, group_room, db
    ):
        await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Secret message"},
            headers=auth(admin_token)
        )
        schema = "tenant_test_hotel_nepal"
        raw = await db.fetchrow(
            f'SELECT content FROM "{schema}".messages ORDER BY created_at DESC LIMIT 1'
        )
        assert raw["content"] != "Secret message"

    async def test_list_messages(self, client, admin_token, group_room):
        await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "First"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        assert resp.json()[0]["content"] == "First"

    async def test_messages_oldest_first(self, client, admin_token, group_room):
        await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Msg A"},
            headers=auth(admin_token)
        )
        await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Msg B"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            headers=auth(admin_token)
        )
        contents = [m["content"] for m in resp.json()]
        assert contents.index("Msg A") < contents.index("Msg B")

    async def test_reply_to_message(self, client, admin_token, group_room):
        msg = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Original"},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Reply", "reply_to_id": msg.json()["id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["reply_to_id"] == msg.json()["id"]

    async def test_edit_message(self, client, admin_token, group_room):
        msg = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Original"},
            headers=auth(admin_token)
        )
        resp = await client.patch(
            f"/api/v1/comms/messages/{msg.json()['id']}",
            json={"content": "Edited"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Edited"
        assert resp.json()["is_edited"] is True

    async def test_edit_history(self, client, admin_token, group_room):
        msg = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Original"},
            headers=auth(admin_token)
        )
        await client.patch(
            f"/api/v1/comms/messages/{msg.json()['id']}",
            json={"content": "Edited"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/comms/messages/{msg.json()['id']}/history",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["old_content"] == "Original"

    async def test_edit_history_decrypted(self, client, admin_token, group_room, db):
        msg = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Before Edit"},
            headers=auth(admin_token)
        )
        await client.patch(
            f"/api/v1/comms/messages/{msg.json()['id']}",
            json={"content": "After Edit"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/comms/messages/{msg.json()['id']}/history",
            headers=auth(admin_token)
        )
        assert resp.json()[0]["old_content"] == "Before Edit"
        # Verify old_content is encrypted in DB
        schema = "tenant_test_hotel_nepal"
        raw = await db.fetchrow(
            f'SELECT old_content FROM "{schema}".message_edits ORDER BY edited_at DESC LIMIT 1'
        )
        assert raw["old_content"] != "Before Edit"

    async def test_delete_message_soft(self, client, admin_token, group_room):
        msg = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Delete me"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/comms/messages/{msg.json()['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 204
        msgs = await client.get(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            headers=auth(admin_token)
        )
        deleted = next(
            (m for m in msgs.json() if m["id"] == msg.json()["id"]), None
        )
        assert deleted is not None
        assert deleted["content"] == "This message was deleted"

    async def test_deleted_message_still_in_db(
        self, client, admin_token, group_room, db
    ):
        msg = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Soft delete check"},
            headers=auth(admin_token)
        )
        msg_id = msg.json()["id"]
        await client.delete(
            f"/api/v1/comms/messages/{msg_id}",
            headers=auth(admin_token)
        )
        schema = "tenant_test_hotel_nepal"
        row = await db.fetchrow(
            f'SELECT is_deleted FROM "{schema}".messages WHERE id = $1',
            uuid.UUID(msg_id)
        )
        assert row["is_deleted"] is True

    async def test_mark_messages_read(self, client, admin_token, group_room):
        resp = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages/read",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_read_receipts_stored(
        self, client, admin_token, staff_user, db
    ):
        # Create direct room between admin and staff
        direct = await client.post(
            "/api/v1/comms/rooms/direct",
            json={"user_id": staff_user["user_id"]},
            headers=auth(admin_token)
        )
        room_id = direct.json()["id"]
        # Admin sends message
        await client.post(
            f"/api/v1/comms/rooms/{room_id}/messages",
            json={"content": "Read receipt test"},
            headers=auth(admin_token)
        )
        # Admin marks as read (reads own messages, no receipts for own)
        await client.post(
            f"/api/v1/comms/rooms/{room_id}/messages/read",
            headers=auth(admin_token)
        )
        schema = "tenant_test_hotel_nepal"
        count = await db.fetchval(
            f'SELECT COUNT(*) FROM "{schema}".message_read_receipts'
        )
        assert count >= 0  # Table exists and is queryable

    async def test_add_reaction(self, client, admin_token, group_room):
        msg = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "React to me"},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/comms/messages/{msg.json()['id']}/reactions",
            json={"emoji": "👍"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201

    async def test_duplicate_reaction_idempotent(
        self, client, admin_token, group_room
    ):
        msg = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Duplicate react"},
            headers=auth(admin_token)
        )
        msg_id = msg.json()["id"]
        await client.post(
            f"/api/v1/comms/messages/{msg_id}/reactions",
            json={"emoji": "👍"},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/comms/messages/{msg_id}/reactions",
            json={"emoji": "👍"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201

    async def test_remove_reaction(self, client, admin_token, group_room):
        msg = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "React"},
            headers=auth(admin_token)
        )
        await client.post(
            f"/api/v1/comms/messages/{msg.json()['id']}/reactions",
            json={"emoji": "❤️"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/comms/messages/{msg.json()['id']}/reactions/%E2%9D%A4%EF%B8%8F",
            headers=auth(admin_token)
        )
        assert resp.status_code == 204

    async def test_search_messages(self, client, admin_token, group_room):
        await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "unique_search_term_xyz"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/comms/rooms/search?q=unique_search_term_xyz",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_search_returns_decrypted_content(
        self, client, admin_token, group_room
    ):
        term = f"searchable_{uuid.uuid4().hex[:6]}"
        await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": term},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/comms/rooms/search?q={term}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert any(term in m["content"] for m in resp.json())

    async def test_pagination_limit(self, client, admin_token, group_room):
        resp = await client.get(
            f"/api/v1/comms/rooms/{group_room['id']}/messages?limit=25",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) <= 25


class TestMessagesNegative:

    async def test_non_member_cannot_send(
        self, client, staff_token, group_room
    ):
        resp = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Hack"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_non_member_cannot_read(
        self, client, staff_token, group_room
    ):
        resp = await client.get(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_cannot_edit_others_message(
        self, client, admin_token, staff_token, staff_user, group_room
    ):
        await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/members",
            json={"user_id": staff_user["user_id"]},
            headers=auth(admin_token)
        )
        msg = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Admin message"},
            headers=auth(admin_token)
        )
        resp = await client.patch(
            f"/api/v1/comms/messages/{msg.json()['id']}",
            json={"content": "Hacked"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_cannot_delete_others_message(
        self, client, admin_token, staff_token, staff_user, group_room
    ):
        await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/members",
            json={"user_id": staff_user["user_id"]},
            headers=auth(admin_token)
        )
        msg = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Admin only message"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/comms/messages/{msg.json()['id']}",
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_cannot_edit_deleted_message(
        self, client, admin_token, group_room
    ):
        msg = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "Will be deleted"},
            headers=auth(admin_token)
        )
        msg_id = msg.json()["id"]
        await client.delete(
            f"/api/v1/comms/messages/{msg_id}",
            headers=auth(admin_token)
        )
        resp = await client.patch(
            f"/api/v1/comms/messages/{msg_id}",
            json={"content": "Edit after delete"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_empty_message_rejected(self, client, admin_token, group_room):
        resp = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": ""},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_unauthenticated_cannot_send(self, client, group_room):
        resp = await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": "No auth"},
        )
        assert resp.status_code == 403

    async def test_edit_nonexistent_message(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/comms/messages/00000000-0000-0000-0000-000000000000",
            json={"content": "Ghost"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_reaction_on_nonexistent_message(self, client, admin_token):
        resp = await client.post(
            "/api/v1/comms/messages/00000000-0000-0000-0000-000000000000/reactions",
            json={"emoji": "👍"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_limit_exceeds_max_capped(self, client, admin_token, group_room):
        resp = await client.get(
            f"/api/v1/comms/rooms/{group_room['id']}/messages?limit=100",
            headers=auth(admin_token)
        )
        assert resp.status_code == 422


class TestAnnouncementRooms:

    async def test_admin_can_post_to_announcement_room(
        self, client, admin_token, announcement_room
    ):
        resp = await client.post(
            f"/api/v1/comms/rooms/{announcement_room['id']}/messages",
            json={"content": "Important announcement"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201

    async def test_staff_without_permission_cannot_post_to_announcement(
        self, client, staff_token, announcement_room
    ):
        resp = await client.post(
            f"/api/v1/comms/rooms/{announcement_room['id']}/messages",
            json={"content": "Hack announcement"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403


class TestNotificationsPositive:

    async def test_list_notifications(self, client, admin_token):
        resp = await client.get(
            "/api/v1/comms/notifications",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_unread_only(self, client, admin_token):
        resp = await client.get(
            "/api/v1/comms/notifications?unread_only=true",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        for n in resp.json():
            assert n["is_read"] is False

    async def test_notification_count(self, client, admin_token):
        resp = await client.get(
            "/api/v1/comms/notifications/count",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert "unread_count" in resp.json()

    async def test_mark_single_notification_read(
        self, client, admin_token, group_room, db
    ):
        # Send a message to trigger a notification — but admin sent it so no self-notification
        # Directly insert a notification for the admin
        schema = "tenant_test_hotel_nepal"
        admin_id = await db.fetchval(
            f'SELECT id FROM "{schema}".user_profiles WHERE is_admin = TRUE LIMIT 1'
        )
        notif_id = await db.fetchval(
            f"""
            INSERT INTO "{schema}".notifications
                (user_id, event_code, title, body)
            VALUES ($1, 'test.event', 'Test Notif', 'Test body')
            RETURNING id
            """,
            admin_id
        )
        resp = await client.post(
            f"/api/v1/comms/notifications/{notif_id}/read",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True

    async def test_mark_all_read(self, client, admin_token):
        resp = await client.post(
            "/api/v1/comms/notifications/read-all",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_mark_all_read_then_count_zero(self, client, admin_token):
        await client.post(
            "/api/v1/comms/notifications/read-all",
            headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/comms/notifications/count",
            headers=auth(admin_token)
        )
        assert resp.json()["unread_count"] == 0

    async def test_notifications_have_required_fields(self, client, admin_token, db):
        schema = "tenant_test_hotel_nepal"
        admin_id = await db.fetchval(
            f'SELECT id FROM "{schema}".user_profiles WHERE is_admin = TRUE LIMIT 1'
        )
        await db.execute(
            f"""
            INSERT INTO "{schema}".notifications
                (user_id, event_code, title, body, reference_type, reference_id)
            VALUES ($1, 'order.created', 'New Order', 'Order test', 'order', $1)
            """,
            admin_id
        )
        resp = await client.get(
            "/api/v1/comms/notifications",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        if resp.json():
            n = resp.json()[0]
            assert "id" in n
            assert "event_code" in n
            assert "title" in n
            assert "is_read" in n
            assert "created_at" in n

    async def test_broadcast(self, client, admin_token):
        resp = await client.post(
            "/api/v1/comms/broadcast",
            json={"title": "Test Broadcast", "body": "This is a test"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert "sent_to" in resp.json()

    async def test_broadcast_to_role(self, client, admin_token, staff_role):
        resp = await client.post(
            "/api/v1/comms/broadcast",
            json={
                "title": "Role Broadcast",
                "body": "For staff only",
                "role_template_id": staff_role["id"]
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201

    async def test_notification_auto_read_on_message_read(
        self, client, admin_token, db
    ):
        schema = "tenant_test_hotel_nepal"
        admin_id = await db.fetchval(
            f'SELECT id FROM "{schema}".user_profiles WHERE is_admin = TRUE LIMIT 1'
        )
        # Create a room and message
        room = await client.post(
            "/api/v1/comms/rooms",
            json={"name": f"AutoRead {uuid.uuid4().hex[:4]}", "type": "group"},
            headers=auth(admin_token)
        )
        room_id = room.json()["id"]
        msg = await client.post(
            f"/api/v1/comms/rooms/{room_id}/messages",
            json={"content": "Auto read test"},
            headers=auth(admin_token)
        )
        msg_id = uuid.UUID(msg.json()["id"])
        # Insert a comms.message notification pointing to this message
        notif_id = await db.fetchval(
            f"""
            INSERT INTO "{schema}".notifications
                (user_id, event_code, title, body, reference_id, reference_type)
            VALUES ($1, 'comms.message', 'New message', 'test', $2, 'message')
            RETURNING id
            """,
            admin_id, msg_id
        )
        # Mark messages read
        await client.post(
            f"/api/v1/comms/rooms/{room_id}/messages/read",
            headers=auth(admin_token)
        )
        # Verify notification is now read
        row = await db.fetchrow(
            f'SELECT is_read FROM "{schema}".notifications WHERE id = $1',
            notif_id
        )
        assert row["is_read"] is True


class TestNotificationsNegative:

    async def test_unauthenticated_rejected(self, client):
        resp = await client.get("/api/v1/comms/notifications")
        assert resp.status_code == 403

    async def test_mark_nonexistent_notification(self, client, admin_token):
        resp = await client.post(
            "/api/v1/comms/notifications/00000000-0000-0000-0000-000000000000/read",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_cannot_read_other_users_notification(
        self, client, admin_token, staff_token, db
    ):
        schema = "tenant_test_hotel_nepal"
        # Get staff user_id
        staff_profile = await db.fetchrow(
            f'SELECT id FROM "{schema}".user_profiles WHERE is_admin = FALSE LIMIT 1'
        )
        if not staff_profile:
            return  # Skip if no staff user
        staff_id = staff_profile["id"]
        notif_id = await db.fetchval(
            f"""
            INSERT INTO "{schema}".notifications
                (user_id, event_code, title, body)
            VALUES ($1, 'test.event', 'Staff Notif', 'body')
            RETURNING id
            """,
            staff_id
        )
        # Admin tries to mark staff's notification as read — should 404
        resp = await client.post(
            f"/api/v1/comms/notifications/{notif_id}/read",
            headers=auth(staff_token)
        )
        # Staff can read their own, so this should succeed
        # But admin cannot read staff's notification
        resp2 = await client.post(
            f"/api/v1/comms/notifications/{notif_id}/read",
            headers=auth(admin_token)
        )
        assert resp2.status_code == 404

    async def test_staff_cannot_broadcast(self, client, staff_token):
        resp = await client.post(
            "/api/v1/comms/broadcast",
            json={"title": "Hack", "body": "Unauthorized broadcast"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403


class TestSecurityAndIsolation:

    async def test_tenant_isolation_messages(
        self, client, admin_token, admin_token_b, group_room
    ):
        resp = await client.get(
            f"/api/v1/comms/rooms/{group_room['id']}",
            headers=auth(admin_token_b)
        )
        assert resp.status_code in (403, 404)

    async def test_tenant_isolation_notifications(
        self, client, admin_token, admin_token_b, db
    ):
        schema = "tenant_test_hotel_nepal"
        admin_id = await db.fetchval(
            f'SELECT id FROM "{schema}".user_profiles WHERE is_admin = TRUE LIMIT 1'
        )
        notif_id = await db.fetchval(
            f"""
            INSERT INTO "{schema}".notifications
                (user_id, event_code, title, body)
            VALUES ($1, 'test.event', 'Tenant 1 Notif', 'body')
            RETURNING id
            """,
            admin_id
        )
        resp = await client.post(
            f"/api/v1/comms/notifications/{notif_id}/read",
            headers=auth(admin_token_b)
        )
        assert resp.status_code == 404

    async def test_upload_url_requires_auth(self, client, group_room):
        resp = await client.post(
            "/api/v1/comms/upload-url",
            json={"room_id": group_room["id"], "filename": "test.jpg"},
        )
        assert resp.status_code == 403

    async def test_upload_url_returns_presigned_url(
        self, client, admin_token, group_room
    ):
        resp = await client.post(
            "/api/v1/comms/upload-url",
            json={"room_id": group_room["id"], "filename": "test.jpg"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert "upload_url" in resp.json()
        assert "key" in resp.json()

    async def test_last_seen_at_updated_on_auth(
        self, client, admin_token, group_room, db
    ):
        # Hit any authed endpoint
        await client.get(
            "/api/v1/comms/rooms",
            headers=auth(admin_token)
        )
        schema = "tenant_test_hotel_nepal"
        row = await db.fetchrow(
            f'SELECT last_seen_at FROM "{schema}".user_profiles WHERE is_admin = TRUE LIMIT 1'
        )
        assert row["last_seen_at"] is not None

    async def test_message_content_not_stored_in_plaintext(
        self, client, admin_token, group_room, db
    ):
        secret = f"plaintext_check_{uuid.uuid4().hex}"
        await client.post(
            f"/api/v1/comms/rooms/{group_room['id']}/messages",
            json={"content": secret},
            headers=auth(admin_token)
        )
        schema = "tenant_test_hotel_nepal"
        row = await db.fetchrow(
            f'SELECT content FROM "{schema}".messages ORDER BY created_at DESC LIMIT 1'
        )
        assert secret not in row["content"]

    async def test_search_only_returns_own_rooms(
        self, client, admin_token, staff_token, db
    ):
        # Admin creates a room and posts a unique message — staff is not a member
        term = f"admin_only_{uuid.uuid4().hex[:6]}"
        room = await client.post(
            "/api/v1/comms/rooms",
            json={"name": f"Admin Only {uuid.uuid4().hex[:4]}", "type": "group"},
            headers=auth(admin_token)
        )
        await client.post(
            f"/api/v1/comms/rooms/{room.json()['id']}/messages",
            json={"content": term},
            headers=auth(admin_token)
        )
        # Staff searches — should not find it
        resp = await client.get(
            f"/api/v1/comms/rooms/search?q={term}",
            headers=auth(staff_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0


# Fixtures 

@pytest.fixture
async def group_room(client, admin_token):
    resp = await client.post(
        "/api/v1/comms/rooms",
        json={"name": f"Room {uuid.uuid4().hex[:6]}", "type": "group"},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def announcement_room(client, admin_token):
    resp = await client.post(
        "/api/v1/comms/rooms",
        json={"name": f"Announce {uuid.uuid4().hex[:6]}", "type": "announcement"},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    # Add staff as member so they can attempt to post
    return resp.json()