import pytest
from tests.conftest import auth


class TestHousekeepingTaskPositive:

    async def test_create_cleaning_task(self, client, admin_token, room):
        resp = await client.post(
            "/api/v1/housekeeping/tasks",
            json={"room_id": room["id"], "task_type": "cleaning"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["task_type"] == "cleaning"
        assert data["room_id"] == room["id"]

    async def test_create_task_sets_room_to_cleaning(self, client, admin_token, room):
        await client.post(
            "/api/v1/housekeeping/tasks",
            json={"room_id": room["id"], "task_type": "cleaning"},
            headers=auth(admin_token)
        )
        room_resp = await client.get(
            f"/api/v1/hotel/rooms/{room['id']}",
            headers=auth(admin_token)
        )
        assert room_resp.json()["status"] == "cleaning"

    async def test_create_task_with_notes(self, client, admin_token, room):
        resp = await client.post(
            "/api/v1/housekeeping/tasks",
            json={"room_id": room["id"], "task_type": "turndown", "notes": "VIP guest"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["notes"] == "VIP guest"

    async def test_list_tasks(self, client, admin_token, hk_task):
        resp = await client.get(
            "/api/v1/housekeeping/tasks",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.json()]
        assert hk_task["id"] in ids

    async def test_filter_by_room(self, client, admin_token, hk_task, room):
        resp = await client.get(
            f"/api/v1/housekeeping/tasks?room_id={room['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert all(t["room_id"] == room["id"] for t in resp.json())

    async def test_filter_by_status(self, client, admin_token, hk_task):
        resp = await client.get(
            "/api/v1/housekeeping/tasks?status=pending",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert all(t["status"] == "pending" for t in resp.json())

    async def test_get_single_task(self, client, admin_token, hk_task):
        resp = await client.get(
            f"/api/v1/housekeeping/tasks/{hk_task['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == hk_task["id"]

    async def test_update_to_in_progress(self, client, admin_token, hk_task):
        resp = await client.patch(
            f"/api/v1/housekeeping/tasks/{hk_task['id']}",
            json={"status": "in_progress"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["started_at"] is not None

    async def test_update_to_done_sets_room_available(self, client, admin_token, hk_task, room):
        await client.patch(
            f"/api/v1/housekeeping/tasks/{hk_task['id']}",
            json={"status": "in_progress"},
            headers=auth(admin_token)
        )
        resp = await client.patch(
            f"/api/v1/housekeeping/tasks/{hk_task['id']}",
            json={"status": "done"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["completed_at"] is not None
        room_resp = await client.get(
            f"/api/v1/hotel/rooms/{room['id']}",
            headers=auth(admin_token)
        )
        assert room_resp.json()["status"] == "available"

    async def test_verify_task(self, client, admin_token, hk_task):
        await client.patch(
            f"/api/v1/housekeeping/tasks/{hk_task['id']}",
            json={"status": "in_progress"},
            headers=auth(admin_token)
        )
        await client.patch(
            f"/api/v1/housekeeping/tasks/{hk_task['id']}",
            json={"status": "done"},
            headers=auth(admin_token)
        )
        resp = await client.patch(
            f"/api/v1/housekeeping/tasks/{hk_task['id']}",
            json={"status": "verified"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "verified"
        assert data["verified_at"] is not None
        assert data["verified_by"] is not None

    async def test_delete_pending_task(self, client, admin_token, room):
        create = await client.post(
            "/api/v1/housekeeping/tasks",
            json={"room_id": room["id"], "task_type": "inspection"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/housekeeping/tasks/{create.json()['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_kit_list_empty(self, client, admin_token, room_type):
        resp = await client.get(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/kit",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_kit_upsert(self, client, admin_token, room_type, hk_ingredient):
        resp = await client.put(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/kit",
            json={"ingredient_id": hk_ingredient["id"], "quantity_per_turn": "2.0"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert float(resp.json()["quantity_per_turn"]) == 2.0

    async def test_kit_upsert_updates_quantity(self, client, admin_token, room_type, hk_ingredient):
        await client.put(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/kit",
            json={"ingredient_id": hk_ingredient["id"], "quantity_per_turn": "1.0"},
            headers=auth(admin_token)
        )
        resp = await client.put(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/kit",
            json={"ingredient_id": hk_ingredient["id"], "quantity_per_turn": "4.0"},
            headers=auth(admin_token)
        )
        assert float(resp.json()["quantity_per_turn"]) == 4.0

    async def test_kit_delete(self, client, admin_token, room_type, hk_ingredient):
        await client.put(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/kit",
            json={"ingredient_id": hk_ingredient["id"], "quantity_per_turn": "2.0"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/kit/{hk_ingredient['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200


class TestHousekeepingTaskNegative:

    async def test_invalid_task_type(self, client, admin_token, room):
        resp = await client.post(
            "/api/v1/housekeeping/tasks",
            json={"room_id": room["id"], "task_type": "deep_clean"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_task_not_found(self, client, admin_token):
        resp = await client.get(
            "/api/v1/housekeeping/tasks/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_delete_non_pending_fails(self, client, admin_token, hk_task):
        await client.patch(
            f"/api/v1/housekeeping/tasks/{hk_task['id']}",
            json={"status": "in_progress"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/housekeeping/tasks/{hk_task['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_unauthenticated_rejected(self, client):
        resp = await client.get("/api/v1/housekeeping/tasks")
        assert resp.status_code == 403

    async def test_kit_invalid_room_type(self, client, admin_token, hk_ingredient):
        resp = await client.put(
            "/api/v1/housekeeping/room-types/00000000-0000-0000-0000-000000000000/kit",
            json={"ingredient_id": hk_ingredient["id"], "quantity_per_turn": "1.0"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_kit_delete_nonexistent(self, client, admin_token, room_type):
        resp = await client.delete(
            f"/api/v1/housekeeping/room-types/{room_type['id']}/kit/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404


# Fixtures 

@pytest.fixture
async def room_type(client, admin_token):
    resp = await client.post(
        "/api/v1/hotel/room-types",
        json={"name": "Deluxe HK", "base_price": "5000.00", "capacity": 2},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def room(client, admin_token, room_type):
    resp = await client.post(
        "/api/v1/hotel/rooms",
        json={"room_type_id": room_type["id"], "room_number": "HK101", "floor": "1"},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def hk_ingredient(client, admin_token):
    resp = await client.post(
        "/api/v1/ingredients",
        json={"name": "Toilet Paper HK", "unit": "piece", "category": "housekeeping"},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def hk_task(client, admin_token, room):
    resp = await client.post(
        "/api/v1/housekeeping/tasks",
        json={"room_id": room["id"], "task_type": "cleaning", "notes": "Standard clean"},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()