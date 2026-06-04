import pytest


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def supplier(client, admin_token):
    resp = await client.post(
        "/api/v1/inventory/suppliers",
        json={"name": "PO Test Supplier Nepal"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def ingredient(client, admin_token):
    resp = await client.post(
        "/api/v1/ingredients",
        json={"name": "PO Test Flour", "unit": "g", "reorder_level": "500"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def draft_po(client, admin_token, supplier):
    resp = await client.post(
        "/api/v1/inventory/purchase-orders",
        json={"supplier_id": supplier["id"], "notes": "Test PO"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    return resp.json()


class TestPurchaseOrderPositive:
    async def test_create_purchase_order(self, client, admin_token, supplier):
        resp = await client.post(
            "/api/v1/inventory/purchase-orders",
            json={"supplier_id": supplier["id"]},
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"
        assert data["po_number"].startswith("PO-")
        assert data["supplier_name"] == supplier["name"]

    async def test_add_item_to_po(self, client, admin_token, draft_po, ingredient):
        resp = await client.post(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/items",
            json={
                "ingredient_id": ingredient["id"],
                "ordered_qty": "10000",
                "unit_price": "0.12",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    async def test_po_total_calculated(self, client, admin_token, draft_po, ingredient):
        resp = await client.post(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/items",
            json={
                "ingredient_id": ingredient["id"],
                "ordered_qty": "10000",
                "unit_price": "0.10",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert float(resp.json()["total_amount"]) == 1000.0

    async def test_approve_purchase_order(self, client, admin_token, draft_po):
        await client.patch(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/status?status=pending_approval",
            headers=auth(admin_token),
        )
        resp = await client.patch(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/status?status=approved",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] is not None

    async def test_receive_po_updates_stock(
        self, client, admin_token, draft_po, ingredient
    ):
        await client.post(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/items",
            json={"ingredient_id": ingredient["id"], "ordered_qty": "5000"},
            headers=auth(admin_token),
        )
        await client.patch(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/status?status=pending_approval",
            headers=auth(admin_token),
        )
        await client.patch(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/status?status=approved",
            headers=auth(admin_token),
        )

        po = await client.get(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}",
            headers=auth(admin_token),
        )
        po_item_id = po.json()["items"][0]["id"]

        before = await client.get(
            f"/api/v1/ingredients/{ingredient['id']}",
            headers=auth(admin_token),
        )
        stock_before = float(before.json()["current_stock"])

        resp = await client.post(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/receive",
            json=[{"po_item_id": po_item_id, "received_qty": "5000"}],
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "received"

        after = await client.get(
            f"/api/v1/ingredients/{ingredient['id']}",
            headers=auth(admin_token),
        )
        assert float(after.json()["current_stock"]) == stock_before + 5000.0

    async def test_partial_receive(
        self, client, admin_token, draft_po, ingredient
    ):
        await client.post(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/items",
            json={"ingredient_id": ingredient["id"], "ordered_qty": "5000"},
            headers=auth(admin_token),
        )
        await client.patch(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/status?status=pending_approval",
            headers=auth(admin_token),
        )
        await client.patch(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/status?status=approved",
            headers=auth(admin_token),
        )
        po = await client.get(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}",
            headers=auth(admin_token),
        )
        po_item_id = po.json()["items"][0]["id"]

        resp = await client.post(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/receive",
            json=[{"po_item_id": po_item_id, "received_qty": "2000"}],
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "partial"

    async def test_list_purchase_orders(self, client, admin_token, draft_po):
        resp = await client.get(
            "/api/v1/inventory/purchase-orders",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_list_filter_by_status(self, client, admin_token, draft_po):
        resp = await client.get(
            "/api/v1/inventory/purchase-orders?status=draft",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        for po in resp.json():
            assert po["status"] == "draft"


class TestPurchaseOrderNegative:
    async def test_invalid_supplier_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/inventory/purchase-orders",
            json={"supplier_id": "00000000-0000-0000-0000-000000000000"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 404

    async def test_duplicate_item_rejected(
        self, client, admin_token, draft_po, ingredient
    ):
        await client.post(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/items",
            json={"ingredient_id": ingredient["id"], "ordered_qty": "1000"},
            headers=auth(admin_token),
        )
        resp = await client.post(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/items",
            json={"ingredient_id": ingredient["id"], "ordered_qty": "500"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 400

    async def test_invalid_status_transition(self, client, admin_token, draft_po):
        resp = await client.patch(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/status?status=received",
            headers=auth(admin_token),
        )
        assert resp.status_code == 400

    async def test_cannot_add_item_to_approved_po(
        self, client, admin_token, draft_po, ingredient
    ):
        await client.patch(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/status?status=pending_approval",
            headers=auth(admin_token),
        )
        await client.patch(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/status?status=approved",
            headers=auth(admin_token),
        )
        resp = await client.post(
            f"/api/v1/inventory/purchase-orders/{draft_po['id']}/items",
            json={"ingredient_id": ingredient["id"], "ordered_qty": "100"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 400

    async def test_staff_cannot_create_po(self, client, staff_token, supplier):
        resp = await client.post(
            "/api/v1/inventory/purchase-orders",
            json={"supplier_id": supplier["id"]},
            headers=auth(staff_token),
        )
        assert resp.status_code == 403