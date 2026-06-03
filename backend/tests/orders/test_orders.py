import pytest
from tests.conftest import auth


@pytest.fixture
async def table(client, admin_token):
    section = await client.post(
        "/api/v1/floor/sections",
        json={"name": "Order Test Section"},
        headers=auth(admin_token)
    )
    if section.status_code == 400:
        sections = await client.get("/api/v1/floor/sections", headers=auth(admin_token))
        sid = next(s["id"] for s in sections.json() if s["name"] == "Order Test Section")
    else:
        sid = section.json()["id"]

    resp = await client.post(
        "/api/v1/floor/tables",
        json={"table_number": "ORD-T-01", "capacity": 4, "section_id": sid},
        headers=auth(admin_token)
    )
    if resp.status_code == 400:
        tables = await client.get("/api/v1/floor/tables", headers=auth(admin_token))
        return next(t for t in tables.json() if t["table_number"] == "ORD-T-01")
    assert resp.status_code == 201
    return resp.json()


class TestOrderPositive:

    async def test_create_dine_in_order(self, client, admin_token, table):
        resp = await client.post(
            "/api/v1/orders",
            json={"order_type": "dine_in", "table_id": table["id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["order_type"] == "dine_in"
        assert data["status"] == "open"
        assert data["table_id"] == table["id"]
        assert data["table_number"] == table["table_number"]
        assert data["order_number"].startswith("ORD-")

    async def test_create_takeaway_order(self, client, admin_token):
        resp = await client.post(
            "/api/v1/orders",
            json={"order_type": "takeaway"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["order_type"] == "takeaway"

    async def test_order_appears_in_list(self, client, admin_token):
        create = await client.post(
            "/api/v1/orders",
            json={"order_type": "takeaway"},
            headers=auth(admin_token)
        )
        order_id = create.json()["id"]
        resp = await client.get("/api/v1/orders", headers=auth(admin_token))
        assert resp.status_code == 200
        ids = [o["id"] for o in resp.json()]
        assert order_id in ids

    async def test_get_single_order(self, client, admin_token):
        create = await client.post(
            "/api/v1/orders",
            json={"order_type": "takeaway"},
            headers=auth(admin_token)
        )
        order_id = create.json()["id"]
        resp = await client.get(
            f"/api/v1/orders/{order_id}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == order_id

    async def test_list_orders_filtered_by_status(self, client, admin_token):
        await client.post(
            "/api/v1/orders",
            json={"order_type": "takeaway"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/orders?status=open",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        for order in resp.json():
            assert order["status"] == "open"

    async def test_update_order_status(self, client, admin_token):
        create = await client.post(
            "/api/v1/orders",
            json={"order_type": "takeaway"},
            headers=auth(admin_token)
        )
        order_id = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "cancelled"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    async def test_table_freed_when_order_cancelled(self, client, admin_token, table):
        # Create a fresh available table
        t = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "ORD-FREE-T-01"},
            headers=auth(admin_token)
        )
        if t.status_code == 400:
            tables = await client.get("/api/v1/floor/tables", headers=auth(admin_token))
            tid = next(t["id"] for t in tables.json() if t["table_number"] == "ORD-FREE-T-01")
        else:
            tid = t.json()["id"]

        create = await client.post(
            "/api/v1/orders",
            json={"order_type": "dine_in", "table_id": tid},
            headers=auth(admin_token)
        )
        order_id = create.json()["id"]

        await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "cancelled"},
            headers=auth(admin_token)
        )
        table_resp = await client.get(
            f"/api/v1/floor/tables/{tid}",
            headers=auth(admin_token)
        )
        assert table_resp.json()["status"] == "available"

    async def test_staff_can_create_order(self, client, staff_token):
        resp = await client.post(
            "/api/v1/orders",
            json={"order_type": "takeaway"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 201

    async def test_order_number_is_unique(self, client, admin_token):
        r1 = await client.post(
            "/api/v1/orders",
            json={"order_type": "takeaway"},
            headers=auth(admin_token)
        )
        r2 = await client.post(
            "/api/v1/orders",
            json={"order_type": "takeaway"},
            headers=auth(admin_token)
        )
        assert r1.json()["order_number"] != r2.json()["order_number"]


class TestOrderNegative:

    async def test_get_nonexistent_order(self, client, admin_token):
        resp = await client.get(
            "/api/v1/orders/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_invalid_table_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/orders",
            json={
                "order_type": "dine_in",
                "table_id": "00000000-0000-0000-0000-000000000000"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_cannot_update_cancelled_order(self, client, admin_token):
        create = await client.post(
            "/api/v1/orders",
            json={"order_type": "takeaway"},
            headers=auth(admin_token)
        )
        order_id = create.json()["id"]
        await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "cancelled"},
            headers=auth(admin_token)
        )
        resp = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "served"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_unauthenticated_cannot_list(self, client):
        resp = await client.get("/api/v1/orders")
        assert resp.status_code == 403