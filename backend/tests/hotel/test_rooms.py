import pytest
from tests.conftest import auth


class TestRoomPositive:

    async def test_admin_creates_room(self, client, admin_token, room_type):
        resp = await client.post(
            "/api/v1/hotel/rooms",
            json={
                "room_type_id": room_type["id"],
                "room_number": "201",
                "floor": "2"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["room_number"] == "201"
        assert data["status"] == "available"

    async def test_room_appears_in_list(self, client, admin_token, room):
        resp = await client.get(
            "/api/v1/hotel/rooms",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert str(room["id"]) in ids

    async def test_get_single_room(self, client, admin_token, room):
        resp = await client.get(
            f"/api/v1/hotel/rooms/{room['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["room_number"] == room["room_number"]

    async def test_update_room_status(self, client, admin_token, room):
        resp = await client.patch(
            f"/api/v1/hotel/rooms/{room['id']}",
            json={"status": "maintenance"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "maintenance"

    async def test_filter_rooms_by_type(self, client, admin_token, room, room_type):
        resp = await client.get(
            f"/api/v1/hotel/rooms?room_type_id={room_type['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_filter_rooms_by_status(self, client, admin_token, room):
        resp = await client.get(
            "/api/v1/hotel/rooms?status=available",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_delete_available_room(self, client, admin_token, room_type):
        r = await client.post(
            "/api/v1/hotel/rooms",
            json={"room_type_id": room_type["id"], "room_number": "999"},
            headers=auth(admin_token)
        )
        assert r.status_code == 201
        resp = await client.delete(
            f"/api/v1/hotel/rooms/{r.json()['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_availability_check(self, client, admin_token, room):
        resp = await client.get(
            "/api/v1/hotel/rooms/availability?check_in=2026-08-01&check_out=2026-08-05&adults=1",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_staff_can_list_rooms(self, client, staff_token):
        resp = await client.get(
            "/api/v1/hotel/rooms",
            headers=auth(staff_token)
        )
        assert resp.status_code == 200


class TestRoomNegative:

    async def test_duplicate_room_number_rejected(self, client, admin_token, room):
        resp = await client.post(
            "/api/v1/hotel/rooms",
            json={"room_type_id": room["room_type_id"], "room_number": room["room_number"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_invalid_room_type_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hotel/rooms",
            json={
                "room_type_id": "00000000-0000-0000-0000-000000000000",
                "room_number": "302"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_invalid_status_rejected(self, client, admin_token, room):
        resp = await client.patch(
            f"/api/v1/hotel/rooms/{room['id']}",
            json={"status": "on_fire"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_get_nonexistent_room(self, client, admin_token):
        resp = await client.get(
            "/api/v1/hotel/rooms/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_staff_cannot_create_room(self, client, staff_token, room_type):
        resp = await client.post(
            "/api/v1/hotel/rooms",
            json={"room_type_id": room_type["id"], "room_number": "403"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_list(self, client):
        resp = await client.get("/api/v1/hotel/rooms")
        assert resp.status_code == 403


@pytest.fixture
async def room_type(client, admin_token):
    resp = await client.post(
        "/api/v1/hotel/room-types",
        json={"name": "Room Test Type", "base_price": "3000.00", "max_adults": 2},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def room(client, admin_token, room_type):
    resp = await client.post(
        "/api/v1/hotel/rooms",
        json={"room_type_id": room_type["id"], "room_number": "101", "floor": "1"},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()