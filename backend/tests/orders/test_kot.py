import pytest
from tests.conftest import auth


@pytest.fixture
async def order_with_items(client, admin_token):
    # Create category and items
    cat = await client.post(
        "/api/v1/menu/categories",
        json={"name": "KOT Test Cat"},
        headers=auth(admin_token)
    )
    if cat.status_code == 400:
        cats = await client.get("/api/v1/menu/categories", headers=auth(admin_token))
        cat_id = next(c["id"] for c in cats.json() if c["name"] == "KOT Test Cat")
    else:
        cat_id = cat.json()["id"]

    # Food item
    food = await client.post(
        "/api/v1/menu/items",
        json={"name": "KOT Burger", "category_id": cat_id,
              "price": "350.00", "item_type": "food"},
        headers=auth(admin_token)
    )
    if food.status_code == 400:
        items = await client.get("/api/v1/menu/items", headers=auth(admin_token))
        food_id = next(i["id"] for i in items.json() if i["name"] == "KOT Burger")
    else:
        food_id = food.json()["id"]

    # Drinks item
    drink = await client.post(
        "/api/v1/menu/items",
        json={"name": "KOT Mojito", "category_id": cat_id,
              "price": "250.00", "item_type": "drinks"},
        headers=auth(admin_token)
    )
    if drink.status_code == 400:
        items = await client.get("/api/v1/menu/items", headers=auth(admin_token))
        drink_id = next(i["id"] for i in items.json() if i["name"] == "KOT Mojito")
    else:
        drink_id = drink.json()["id"]

    # Create order
    order = await client.post(
        "/api/v1/orders",
        json={"order_type": "takeaway"},
        headers=auth(admin_token)
    )
    assert order.status_code == 201
    order_id = order.json()["id"]

    # Add food item
    await client.post(
        f"/api/v1/orders/{order_id}/items",
        json={"menu_item_id": food_id, "quantity": 2},
        headers=auth(admin_token)
    )

    # Add drinks item
    await client.post(
        f"/api/v1/orders/{order_id}/items",
        json={"menu_item_id": drink_id, "quantity": 1},
        headers=auth(admin_token)
    )

    return {"order_id": order_id, "food_id": food_id, "drink_id": drink_id}


class TestKOTPositive:

    async def test_generate_kots_creates_food_and_drinks(
        self, client, admin_token, order_with_items
    ):
        resp = await client.post(
            f"/api/v1/orders/{order_with_items['order_id']}/kot",
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        kots = resp.json()
        assert len(kots) == 2
        types = {k["kot_type"] for k in kots}
        assert "food" in types
        assert "drinks" in types

    async def test_kot_number_format(self, client, admin_token, order_with_items):
        resp = await client.post(
            f"/api/v1/orders/{order_with_items['order_id']}/kot",
            headers=auth(admin_token)
        )
        kots = resp.json()
        for kot in kots:
            assert "ORD-" in kot["kot_number"]
            assert kot["kot_number"].endswith("-F") or kot["kot_number"].endswith("-D")

    async def test_kot_initial_status_is_pending(self, client, admin_token, order_with_items):
        resp = await client.post(
            f"/api/v1/orders/{order_with_items['order_id']}/kot",
            headers=auth(admin_token)
        )
        for kot in resp.json():
            assert kot["display_status"] == "pending"

    async def test_items_move_to_preparing_after_kot(
        self, client, admin_token, order_with_items
    ):
        await client.post(
            f"/api/v1/orders/{order_with_items['order_id']}/kot",
            headers=auth(admin_token)
        )
        items = await client.get(
            f"/api/v1/orders/{order_with_items['order_id']}/items",
            headers=auth(admin_token)
        )
        for item in items.json():
            assert item["status"] == "preparing"

    async def test_get_order_kots(self, client, admin_token, order_with_items):
        await client.post(
            f"/api/v1/orders/{order_with_items['order_id']}/kot",
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/orders/{order_with_items['order_id']}/kot",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_pending_kots_list(self, client, admin_token, order_with_items):
        await client.post(
            f"/api/v1/orders/{order_with_items['order_id']}/kot",
            headers=auth(admin_token)
        )
        resp = await client.get("/api/v1/kots/pending", headers=auth(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    async def test_assign_kot(self, client, admin_token, order_with_items, db):
        gen = await client.post(
            f"/api/v1/orders/{order_with_items['order_id']}/kot",
            headers=auth(admin_token)
        )
        kot_id = gen.json()[0]["id"]

        user = await db.fetchrow(
            "SELECT id FROM core.users WHERE email = $1",
            "testadmin@testhotel.com"
        )

        resp = await client.patch(
            f"/api/v1/kots/{kot_id}/assign",
            json={"assigned_to": str(user["id"])},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["display_status"] == "assigned"
        assert resp.json()["assigned_to"] == str(user["id"])

    async def test_mark_kot_printed(self, client, admin_token, order_with_items):
        gen = await client.post(
            f"/api/v1/orders/{order_with_items['order_id']}/kot",
            headers=auth(admin_token)
        )
        kot_id = gen.json()[0]["id"]

        resp = await client.patch(
            f"/api/v1/kots/{kot_id}/print",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["printed_at"] is not None

    async def test_get_kot_html(self, client, admin_token, order_with_items):
        gen = await client.post(
            f"/api/v1/orders/{order_with_items['order_id']}/kot",
            headers=auth(admin_token)
        )
        kot_id = gen.json()[0]["id"]

        resp = await client.get(
            f"/api/v1/kots/{kot_id}/html",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert "<!DOCTYPE html>" in resp.text
        assert "ORDER" in resp.text
        assert "ORD-" in resp.text

    async def test_generate_kots_idempotent(self, client, admin_token, order_with_items):
        await client.post(
            f"/api/v1/orders/{order_with_items['order_id']}/kot",
            headers=auth(admin_token)
        )
        resp2 = await client.post(
            f"/api/v1/orders/{order_with_items['order_id']}/kot",
            headers=auth(admin_token)
        )
        assert resp2.status_code == 201
        assert resp2.json() == []


class TestKOTNegative:

    async def test_generate_kot_nonexistent_order(self, client, admin_token):
        resp = await client.post(
            "/api/v1/orders/00000000-0000-0000-0000-000000000000/kot",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_assign_nonexistent_kot(self, client, admin_token, db):
        user = await db.fetchrow(
            "SELECT id FROM core.users WHERE email = $1",
            "testadmin@testhotel.com"
        )
        resp = await client.patch(
            "/api/v1/kots/00000000-0000-0000-0000-000000000000/assign",
            json={"assigned_to": str(user["id"])},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_unauthenticated_cannot_get_kots(self, client, order_with_items):
        resp = await client.get(
            f"/api/v1/orders/{order_with_items['order_id']}/kot"
        )
        assert resp.status_code == 403