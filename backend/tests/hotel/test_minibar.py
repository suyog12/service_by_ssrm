import pytest
from tests.conftest import auth


class TestMinibarPositive:

    async def test_list_minibar_empty(self, client, admin_token, room_type):
        resp = await client.get(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_upsert_minibar_item(self, client, admin_token, room_type, minibar_ingredient):
        resp = await client.put(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar",
            json={"ingredient_id": minibar_ingredient["id"], "quantity": "2.0"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["room_type_id"] == room_type["id"]
        assert float(data["quantity"]) == 2.0

    async def test_list_minibar_shows_item(self, client, admin_token, room_type, minibar_ingredient):
        await client.put(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar",
            json={"ingredient_id": minibar_ingredient["id"], "quantity": "3.0"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert float(resp.json()[0]["quantity"]) == 3.0

    async def test_upsert_updates_quantity(self, client, admin_token, room_type, minibar_ingredient):
        await client.put(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar",
            json={"ingredient_id": minibar_ingredient["id"], "quantity": "1.0"},
            headers=auth(admin_token)
        )
        resp = await client.put(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar",
            json={"ingredient_id": minibar_ingredient["id"], "quantity": "5.0"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert float(resp.json()["quantity"]) == 5.0

    async def test_delete_minibar_item(self, client, admin_token, room_type, minibar_ingredient):
        await client.put(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar",
            json={"ingredient_id": minibar_ingredient["id"], "quantity": "2.0"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar/{minibar_ingredient['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        list_resp = await client.get(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar",
            headers=auth(admin_token)
        )
        assert list_resp.json() == []

    async def test_multiple_items(self, client, admin_token, room_type):
        for name, qty in [("Water MB", "2.0"), ("Peanuts MB", "1.0"), ("Coke MB", "3.0")]:
            ing = await client.post(
                "/api/v1/ingredients",
                json={"name": name, "unit": "piece", "category": "minibar"},
                headers=auth(admin_token)
            )
            assert ing.status_code == 201
            await client.put(
                f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar",
                json={"ingredient_id": ing.json()["id"], "quantity": qty},
                headers=auth(admin_token)
            )
        resp = await client.get(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar",
            headers=auth(admin_token)
        )
        assert len(resp.json()) == 3


class TestMinibarNegative:

    async def test_invalid_room_type(self, client, admin_token, minibar_ingredient):
        resp = await client.put(
            "/api/v1/housekeeping/room-types/00000000-0000-0000-0000-000000000000/minibar",
            json={"ingredient_id": minibar_ingredient["id"], "quantity": "1.0"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_invalid_ingredient(self, client, admin_token, room_type):
        resp = await client.put(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar",
            json={"ingredient_id": "00000000-0000-0000-0000-000000000000", "quantity": "1.0"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_delete_nonexistent(self, client, admin_token, room_type):
        resp = await client.delete(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_unauthenticated_rejected(self, client, room_type):
        resp = await client.get(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar"
        )
        assert resp.status_code == 403

    async def test_zero_quantity_rejected(self, client, admin_token, room_type, minibar_ingredient):
        resp = await client.put(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/minibar",
            json={"ingredient_id": minibar_ingredient["id"], "quantity": "0"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422


# Fixtures 

@pytest.fixture
async def room_type(client, admin_token):
    resp = await client.post(
        "/api/v1/hotel/room-types",
        json={"name": "Minibar Suite", "base_price": "8000.00", "capacity": 2},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def minibar_ingredient(client, admin_token):
    resp = await client.post(
        "/api/v1/ingredients",
        json={"name": "Snickers Bar", "unit": "piece", "category": "minibar"},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()