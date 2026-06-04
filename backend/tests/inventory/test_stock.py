import pytest


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def ingredient(client, admin_token):
    resp = await client.post(
        "/api/v1/ingredients",
        json={"name": "Stock Test Rice", "unit": "g", "reorder_level": "1000"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    return resp.json()


class TestStockAddPositive:
    async def test_add_stock_increases_current_stock(
        self, client, admin_token, ingredient
    ):
        resp = await client.post(
            "/api/v1/inventory/stock/add",
            json={
                "ingredient_id": ingredient["id"],
                "quantity": "5000",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["quantity_added"] == "5000"
        assert float(data["current_stock"]) == 5000.0

    async def test_add_stock_creates_batch(self, client, admin_token, ingredient):
        resp = await client.post(
            "/api/v1/inventory/stock/add",
            json={
                "ingredient_id": ingredient["id"],
                "quantity": "2000",
                "notes": "Received from Ram Suppliers",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        assert "batch_id" in resp.json()

    async def test_add_stock_with_expiry(self, client, admin_token, ingredient):
        resp = await client.post(
            "/api/v1/inventory/stock/add",
            json={
                "ingredient_id": ingredient["id"],
                "quantity": "3000",
                "expiry_date": "2026-12-31",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 201

    async def test_add_stock_multiple_times_accumulates(
        self, client, admin_token, ingredient
    ):
        await client.post(
            "/api/v1/inventory/stock/add",
            json={"ingredient_id": ingredient["id"], "quantity": "1000"},
            headers=auth(admin_token),
        )
        resp = await client.post(
            "/api/v1/inventory/stock/add",
            json={"ingredient_id": ingredient["id"], "quantity": "500"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        assert float(resp.json()["current_stock"]) == 1500.0

    async def test_add_stock_updates_cost_per_unit(
        self, client, admin_token, ingredient
    ):
        resp = await client.post(
            "/api/v1/inventory/stock/add",
            json={
                "ingredient_id": ingredient["id"],
                "quantity": "1000",
                "cost_per_unit": "0.15",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 201


class TestStockAddNegative:
    async def test_zero_quantity_rejected(self, client, admin_token, ingredient):
        resp = await client.post(
            "/api/v1/inventory/stock/add",
            json={"ingredient_id": ingredient["id"], "quantity": "0"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 422

    async def test_nonexistent_ingredient_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/inventory/stock/add",
            json={
                "ingredient_id": "00000000-0000-0000-0000-000000000000",
                "quantity": "100",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 404

    async def test_staff_cannot_add_stock(self, client, staff_token, ingredient):
        resp = await client.post(
            "/api/v1/inventory/stock/add",
            json={"ingredient_id": ingredient["id"], "quantity": "100"},
            headers=auth(staff_token),
        )
        assert resp.status_code == 403


class TestStockAdjustPositive:
    async def test_adjust_stock_sets_new_level(self, client, admin_token, ingredient):
        await client.post(
            "/api/v1/inventory/stock/add",
            json={"ingredient_id": ingredient["id"], "quantity": "5000"},
            headers=auth(admin_token),
        )
        resp = await client.post(
            "/api/v1/inventory/stock/adjust",
            json={
                "ingredient_id": ingredient["id"],
                "new_stock": "4000",
                "reason": "Physical count correction",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert float(data["new_stock"]) == 4000.0
        assert float(data["previous_stock"]) == 5000.0

    async def test_adjust_stores_reason(self, client, admin_token, ingredient):
        resp = await client.post(
            "/api/v1/inventory/stock/adjust",
            json={
                "ingredient_id": ingredient["id"],
                "new_stock": "100",
                "reason": "Spoilage",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        assert resp.json()["reason"] == "Spoilage"

    async def test_list_adjustments(self, client, admin_token, ingredient):
        await client.post(
            "/api/v1/inventory/stock/adjust",
            json={
                "ingredient_id": ingredient["id"],
                "new_stock": "500",
                "reason": "Test adjustment",
            },
            headers=auth(admin_token),
        )
        resp = await client.get(
            "/api/v1/inventory/stock/adjustments",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_reorder_alert_fires_when_stock_low(
        self, client, admin_token, ingredient
    ):
        await client.post(
            "/api/v1/inventory/stock/adjust",
            json={
                "ingredient_id": ingredient["id"],
                "new_stock": "500",
                "reason": "Testing low stock alert",
            },
            headers=auth(admin_token),
        )
        resp = await client.get(
            "/api/v1/inventory/stock/reorder-alerts",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        ids = [a["ingredient_id"] for a in resp.json()]
        assert ingredient["id"] in ids


class TestStockAdjustNegative:
    async def test_negative_stock_rejected(self, client, admin_token, ingredient):
        resp = await client.post(
            "/api/v1/inventory/stock/adjust",
            json={
                "ingredient_id": ingredient["id"],
                "new_stock": "-10",
                "reason": "Should fail",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 422

    async def test_empty_reason_rejected(self, client, admin_token, ingredient):
        resp = await client.post(
            "/api/v1/inventory/stock/adjust",
            json={
                "ingredient_id": ingredient["id"],
                "new_stock": "100",
                "reason": "",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 422