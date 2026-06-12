import pytest
from tests.conftest import auth


class TestRoomTypePositive:

    async def test_admin_creates_room_type(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hotel/room-types",
            json={
                "name": "Deluxe Mountain View",
                "description": "Stunning mountain views with king bed",
                "base_price": "5000.00",
                "capacity": 2,
                "max_adults": 2,
                "max_children": 1,
                "bed_type": "king",
                "floor_area_sqm": "32.5",
                "view_type": "mountain",
                "amenities": {"wifi": True, "ac": True, "tv": True},
                "image_urls": ["https://r2.example.com/room1.jpg"]
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Deluxe Mountain View"
        assert data["bed_type"] == "king"
        assert data["view_type"] == "mountain"
        assert data["is_active"] is True

    async def test_room_type_appears_in_list(self, client, admin_token, room_type):
        resp = await client.get(
            "/api/v1/hotel/room-types",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert str(room_type["id"]) in ids

    async def test_get_single_room_type(self, client, admin_token, room_type):
        resp = await client.get(
            f"/api/v1/hotel/room-types/{room_type['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == room_type["name"]

    async def test_update_room_type(self, client, admin_token, room_type):
        resp = await client.patch(
            f"/api/v1/hotel/room-types/{room_type['id']}",
            json={"base_price": "6000.00", "description": "Updated description"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert float(resp.json()["base_price"]) == 6000.00

    async def test_deactivate_room_type(self, client, admin_token, room_type):
        resp = await client.patch(
            f"/api/v1/hotel/room-types/{room_type['id']}",
            json={"is_active": False},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_inactive_hidden_from_list(self, client, admin_token, room_type):
        await client.patch(
            f"/api/v1/hotel/room-types/{room_type['id']}",
            json={"is_active": False},
            headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/hotel/room-types",
            headers=auth(admin_token)
        )
        ids = [r["id"] for r in resp.json()]
        assert str(room_type["id"]) not in ids

    async def test_inactive_visible_with_flag(self, client, admin_token, room_type):
        await client.patch(
            f"/api/v1/hotel/room-types/{room_type['id']}",
            json={"is_active": False},
            headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/hotel/room-types?active_only=false",
            headers=auth(admin_token)
        )
        ids = [r["id"] for r in resp.json()]
        assert str(room_type["id"]) in ids

    async def test_staff_can_list_room_types(self, client, staff_token):
        resp = await client.get(
            "/api/v1/hotel/room-types",
            headers=auth(staff_token)
        )
        assert resp.status_code == 200

    async def test_share_card(self, client, admin_token, room_type):
        resp = await client.get(
            f"/api/v1/hotel/room-types/{room_type['id']}/share-card",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == room_type["name"]
        assert "available_count" in data
        assert "image_urls" in data

    async def test_create_pricing_rule(self, client, admin_token, room_type):
        resp = await client.post(
            f"/api/v1/hotel/room-types/{room_type['id']}/pricing-rules",
            json={
                "name": "Peak Season",
                "price": "7500.00",
                "start_date": "2026-10-01",
                "end_date": "2026-12-31"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Peak Season"
        assert float(data["price"]) == 7500.00

    async def test_list_pricing_rules(self, client, admin_token, room_type):
        await client.post(
            f"/api/v1/hotel/room-types/{room_type['id']}/pricing-rules",
            json={"name": "Weekend Rate", "price": "5500.00", "days_of_week": [5, 6]},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/hotel/room-types/{room_type['id']}/pricing-rules",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_delete_room_type(self, client, admin_token):
        rt = await client.post(
            "/api/v1/hotel/room-types",
            json={"name": "To Delete Type", "base_price": "3000.00"},
            headers=auth(admin_token)
        )
        assert rt.status_code == 201
        resp = await client.delete(
            f"/api/v1/hotel/room-types/{rt.json()['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200


class TestRoomTypeNegative:

    async def test_duplicate_name_rejected(self, client, admin_token, room_type):
        resp = await client.post(
            "/api/v1/hotel/room-types",
            json={"name": room_type["name"], "base_price": "3000.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_invalid_bed_type_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hotel/room-types",
            json={"name": "Bad Bed", "base_price": "3000.00", "bed_type": "hammock"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_invalid_view_type_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hotel/room-types",
            json={"name": "Bad View", "base_price": "3000.00", "view_type": "moon"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_zero_price_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hotel/room-types",
            json={"name": "Free Room", "base_price": "0"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_staff_cannot_create(self, client, staff_token):
        resp = await client.post(
            "/api/v1/hotel/room-types",
            json={"name": "Hacker Room", "base_price": "3000.00"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_get_nonexistent(self, client, admin_token):
        resp = await client.get(
            "/api/v1/hotel/room-types/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_cannot_delete_type_with_rooms(self, client, admin_token, room):
        resp = await client.delete(
            f"/api/v1/hotel/room-types/{room['room_type_id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400


@pytest.fixture
async def room_type(client, admin_token):
    resp = await client.post(
        "/api/v1/hotel/room-types",
        json={
            "name": "Standard Room",
            "description": "Comfortable standard room",
            "base_price": "3500.00",
            "max_adults": 2,
            "max_children": 1,
            "bed_type": "double",
            "view_type": "garden"
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def room(client, admin_token, room_type):
    resp = await client.post(
        "/api/v1/hotel/rooms",
        json={
            "room_type_id": room_type["id"],
            "room_number": "101",
            "floor": "1"
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()