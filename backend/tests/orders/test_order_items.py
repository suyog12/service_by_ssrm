import pytest
from tests.conftest import auth


@pytest.fixture
async def order(client, admin_token):
    resp = await client.post(
        "/api/v1/orders",
        json={"order_type": "takeaway"},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def menu_item_for_order(client, admin_token):
    cat = await client.post(
        "/api/v1/menu/categories",
        json={"name": "Order Test Cat"},
        headers=auth(admin_token)
    )
    if cat.status_code == 400:
        cats = await client.get("/api/v1/menu/categories", headers=auth(admin_token))
        cat_id = next(c["id"] for c in cats.json() if c["name"] == "Order Test Cat")
    else:
        cat_id = cat.json()["id"]

    resp = await client.post(
        "/api/v1/menu/items",
        json={"name": "Test Burger", "category_id": cat_id, "price": "350.00"},
        headers=auth(admin_token)
    )
    if resp.status_code == 400:
        items = await client.get("/api/v1/menu/items", headers=auth(admin_token))
        return next(i for i in items.json() if i["name"] == "Test Burger")
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def ingredient_for_order(client, admin_token):
    resp = await client.post(
        "/api/v1/ingredients",
        json={"name": "Order Test Beef", "unit": "grams", "reorder_level": "100"},
        headers=auth(admin_token)
    )
    if resp.status_code == 400:
        items = await client.get("/api/v1/ingredients", headers=auth(admin_token))
        return next(i for i in items.json() if i["name"] == "Order Test Beef")
    assert resp.status_code == 201
    return resp.json()


class TestOrderItemPositive:

    async def test_add_item_to_order(self, client, admin_token, order, menu_item_for_order):
        resp = await client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={"menu_item_id": menu_item_for_order["id"], "quantity": 2},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["menu_item_id"] == menu_item_for_order["id"]
        assert data["quantity"] == 2
        assert data["status"] == "pending"
        assert float(data["unit_price"]) == float(menu_item_for_order["price"])

    async def test_item_name_in_response(self, client, admin_token, order, menu_item_for_order):
        resp = await client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={"menu_item_id": menu_item_for_order["id"], "quantity": 1},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["item_name"] == menu_item_for_order["name"]

    async def test_order_moves_to_in_progress(self, client, admin_token, order, menu_item_for_order):
        await client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={"menu_item_id": menu_item_for_order["id"], "quantity": 1},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/orders/{order['id']}",
            headers=auth(admin_token)
        )
        assert resp.json()["status"] == "in_progress"

    async def test_list_order_items(self, client, admin_token, order, menu_item_for_order):
        await client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={"menu_item_id": menu_item_for_order["id"], "quantity": 1},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/orders/{order['id']}/items",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_update_item_status_to_preparing(
        self, client, admin_token, order, menu_item_for_order
    ):
        add = await client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={"menu_item_id": menu_item_for_order["id"], "quantity": 1},
            headers=auth(admin_token)
        )
        item_id = add.json()["id"]
        resp = await client.patch(
            f"/api/v1/orders/{order['id']}/items/{item_id}/status",
            json={"status": "preparing"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "preparing"

    async def test_item_served_deducts_stock(
        self, client, admin_token, order,
        menu_item_for_order, ingredient_for_order, db
    ):
        schema = "tenant_test_hotel_nepal"

        # Set stock to 500g
        await db.execute(
            f'UPDATE "{schema}".ingredients SET current_stock = 500 WHERE id = $1',
            ingredient_for_order["id"]
        )

        # Link ingredient to menu item — 150g per serving
        await client.post(
            f"/api/v1/menu/items/{menu_item_for_order['id']}/ingredients",
            json={
                "ingredient_id": ingredient_for_order["id"],
                "quantity_used": "150"
            },
            headers=auth(admin_token)
        )

        # Add item to order (qty 2)
        add = await client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={"menu_item_id": menu_item_for_order["id"], "quantity": 2},
            headers=auth(admin_token)
        )
        item_id = add.json()["id"]

        # Mark as served — should deduct 150 * 2 = 300g
        await client.patch(
            f"/api/v1/orders/{order['id']}/items/{item_id}/status",
            json={"status": "served"},
            headers=auth(admin_token)
        )

        row = await db.fetchrow(
            f'SELECT current_stock FROM "{schema}".ingredients WHERE id = $1',
            ingredient_for_order["id"]
        )
        assert float(row["current_stock"]) == 200.0

    async def test_add_special_instruction(self, client, admin_token, order, menu_item_for_order):
        resp = await client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "menu_item_id": menu_item_for_order["id"],
                "quantity": 1,
                "special_instruction": "No onions please"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["special_instruction"] == "No onions please"

    async def test_cancel_order_item(self, client, admin_token, order, menu_item_for_order):
        add = await client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={"menu_item_id": menu_item_for_order["id"], "quantity": 1},
            headers=auth(admin_token)
        )
        item_id = add.json()["id"]
        resp = await client.delete(
            f"/api/v1/orders/{order['id']}/items/{item_id}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200


class TestOrderItemNegative:

    async def test_add_unavailable_item_rejected(self, client, admin_token, order):
        cat = await client.post(
            "/api/v1/menu/categories",
            json={"name": "Unavail Cat"},
            headers=auth(admin_token)
        )
        if cat.status_code == 400:
            cats = await client.get("/api/v1/menu/categories", headers=auth(admin_token))
            cat_id = next(c["id"] for c in cats.json() if c["name"] == "Unavail Cat")
        else:
            cat_id = cat.json()["id"]

        item = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Unavailable Item",
                "category_id": cat_id,
                "price": "100.00",
                "is_available": False
            },
            headers=auth(admin_token)
        )
        if item.status_code == 400:
            items = await client.get("/api/v1/menu/items", headers=auth(admin_token))
            item_id = next(i["id"] for i in items.json() if i["name"] == "Unavailable Item")
        else:
            item_id = item.json()["id"]

        resp = await client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={"menu_item_id": item_id, "quantity": 1},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_add_item_to_cancelled_order(
        self, client, admin_token, menu_item_for_order
    ):
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
        resp = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={"menu_item_id": menu_item_for_order["id"], "quantity": 1},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_zero_quantity_rejected(self, client, admin_token, order, menu_item_for_order):
        resp = await client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={"menu_item_id": menu_item_for_order["id"], "quantity": 0},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_nonexistent_item_rejected(self, client, admin_token, order):
        resp = await client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "menu_item_id": "00000000-0000-0000-0000-000000000000",
                "quantity": 1
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_update_cancelled_item_rejected(
        self, client, admin_token, order, menu_item_for_order
    ):
        add = await client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={"menu_item_id": menu_item_for_order["id"], "quantity": 1},
            headers=auth(admin_token)
        )
        item_id = add.json()["id"]
        await client.delete(
            f"/api/v1/orders/{order['id']}/items/{item_id}",
            headers=auth(admin_token)
        )
        resp = await client.patch(
            f"/api/v1/orders/{order['id']}/items/{item_id}/status",
            json={"status": "preparing"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400