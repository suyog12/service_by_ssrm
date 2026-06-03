import pytest
from tests.conftest import auth


# Shared fixture: one category to attach items to

@pytest.fixture
async def menu_category(client, admin_token):
    resp = await client.post(
        "/api/v1/menu/categories",
        json={"name": "Test Food Category"},
        headers=auth(admin_token)
    )
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        cats = await client.get("/api/v1/menu/categories", headers=auth(admin_token))
        for c in cats.json():
            if c["name"] == "Test Food Category":
                return c
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def menu_category_b(client, admin_token_b):
    resp = await client.post(
        "/api/v1/menu/categories",
        json={"name": "Tenant B Category"},
        headers=auth(admin_token_b)
    )
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        cats = await client.get("/api/v1/menu/categories", headers=auth(admin_token_b))
        for c in cats.json():
            if c["name"] == "Tenant B Category":
                return c
    assert resp.status_code == 201
    return resp.json()


class TestMenuItemPositive:

    async def test_admin_creates_item(self, client, admin_token, menu_category):
        resp = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Butter Chicken",
                "category_id": menu_category["id"],
                "price": "450.00",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Butter Chicken"
        assert float(data["price"]) == 450.00
        assert float(data["tax_rate"]) == 13.00
        assert data["station"] is None
        assert data["is_available"] is True
        assert data["category_id"] == menu_category["id"]

    async def test_item_has_category_name(self, client, admin_token, menu_category):
        resp = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Dal Makhani",
                "category_id": menu_category["id"],
                "price": "320.00",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["category_name"] == menu_category["name"]

    async def test_create_item_with_station(self, client, admin_token, menu_category):
        resp = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Mojito",
                "category_id": menu_category["id"],
                "price": "250.00",
                "station": "bar",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["station"] == "bar"

    async def test_create_item_with_all_stations(self, client, admin_token, menu_category):
        for station in ["kitchen", "bar", "grill"]:
            resp = await client.post(
                "/api/v1/menu/items",
                json={
                    "name": f"Station Test {station}",
                    "category_id": menu_category["id"],
                    "price": "100.00",
                    "station": station,
                },
                headers=auth(admin_token)
            )
            assert resp.status_code == 201
            assert resp.json()["station"] == station

    async def test_create_item_with_custom_tax_rate(self, client, admin_token, menu_category):
        resp = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Zero Tax Item",
                "category_id": menu_category["id"],
                "price": "100.00",
                "tax_rate": "0.00",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert float(resp.json()["tax_rate"]) == 0.00

    async def test_create_item_with_item_type_drinks(self, client, admin_token, menu_category):
        resp = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Fresh Lime Soda",
                "category_id": menu_category["id"],
                "price": "150.00",
                "item_type": "drinks",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["item_type"] == "drinks"

    async def test_item_type_defaults_to_food(self, client, admin_token, menu_category):
        resp = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Plain Rice",
                "category_id": menu_category["id"],
                "price": "120.00",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["item_type"] == "food"

    async def test_item_appears_in_list(self, client, admin_token, menu_category):
        await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Paneer Tikka",
                "category_id": menu_category["id"],
                "price": "380.00",
            },
            headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/menu/items",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()]
        assert "Paneer Tikka" in names

    async def test_list_items_filtered_by_category(self, client, admin_token, menu_category):
        resp = await client.get(
            f"/api/v1/menu/items?category_id={menu_category['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        for item in resp.json():
            assert item["category_id"] == menu_category["id"]

    async def test_get_single_item(self, client, admin_token, menu_category):
        create = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Chicken Momo",
                "category_id": menu_category["id"],
                "price": "220.00",
            },
            headers=auth(admin_token)
        )
        item_id = create.json()["id"]
        resp = await client.get(
            f"/api/v1/menu/items/{item_id}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == item_id
        assert resp.json()["name"] == "Chicken Momo"

    async def test_update_item_price(self, client, admin_token, menu_category):
        create = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Veg Burger",
                "category_id": menu_category["id"],
                "price": "180.00",
            },
            headers=auth(admin_token)
        )
        item_id = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/menu/items/{item_id}",
            json={"price": "200.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert float(resp.json()["price"]) == 200.00

    async def test_update_item_availability(self, client, admin_token, menu_category):
        create = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Seasonal Special",
                "category_id": menu_category["id"],
                "price": "500.00",
            },
            headers=auth(admin_token)
        )
        item_id = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/menu/items/{item_id}",
            json={"is_available": False},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_available"] is False

    async def test_update_item_station(self, client, admin_token, menu_category):
        create = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Grilled Fish",
                "category_id": menu_category["id"],
                "price": "600.00",
            },
            headers=auth(admin_token)
        )
        item_id = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/menu/items/{item_id}",
            json={"station": "grill"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["station"] == "grill"

    async def test_delete_item(self, client, admin_token, menu_category):
        create = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "ItemToDelete",
                "category_id": menu_category["id"],
                "price": "100.00",
            },
            headers=auth(admin_token)
        )
        item_id = create.json()["id"]
        resp = await client.delete(
            f"/api/v1/menu/items/{item_id}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()

    async def test_staff_can_list_items(self, client, staff_token):
        resp = await client.get(
            "/api/v1/menu/items",
            headers=auth(staff_token)
        )
        assert resp.status_code == 200

    async def test_staff_can_get_single_item(self, client, staff_token, admin_token, menu_category):
        create = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Staff Readable Item",
                "category_id": menu_category["id"],
                "price": "150.00",
            },
            headers=auth(admin_token)
        )
        item_id = create.json()["id"]
        resp = await client.get(
            f"/api/v1/menu/items/{item_id}",
            headers=auth(staff_token)
        )
        assert resp.status_code == 200


class TestMenuItemNegative:

    async def test_invalid_category_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Orphan Item",
                "category_id": "00000000-0000-0000-0000-000000000000",
                "price": "100.00",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "category" in resp.json()["detail"].lower()

    async def test_negative_price_rejected(self, client, admin_token, menu_category):
        resp = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Bad Price Item",
                "category_id": menu_category["id"],
                "price": "-50.00",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_empty_name_rejected(self, client, admin_token, menu_category):
        resp = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "",
                "category_id": menu_category["id"],
                "price": "100.00",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code in [400, 422]

    async def test_invalid_station_rejected(self, client, admin_token, menu_category):
        resp = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Bad Station Item",
                "category_id": menu_category["id"],
                "price": "100.00",
                "station": "oven",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_invalid_item_type_rejected(self, client, admin_token, menu_category):
        resp = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Bad Type Item",
                "category_id": menu_category["id"],
                "price": "100.00",
                "item_type": "snacks",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_get_nonexistent_item(self, client, admin_token):
        resp = await client.get(
            "/api/v1/menu/items/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_delete_nonexistent_item(self, client, admin_token):
        resp = await client.delete(
            "/api/v1/menu/items/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_staff_cannot_create_item(self, client, staff_token, menu_category):
        resp = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Unauthorized Item",
                "category_id": menu_category["id"],
                "price": "100.00",
            },
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_delete_item(self, client, staff_token, admin_token, menu_category):
        create = await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Protected Item",
                "category_id": menu_category["id"],
                "price": "100.00",
            },
            headers=auth(admin_token)
        )
        item_id = create.json()["id"]
        resp = await client.delete(
            f"/api/v1/menu/items/{item_id}",
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_list_items(self, client):
        resp = await client.get("/api/v1/menu/items")
        assert resp.status_code == 403


class TestMenuItemSecurity:

    async def test_tenant_isolation_items(
        self, client, admin_token, admin_token_b,
        menu_category, menu_category_b
    ):
        await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Tenant A Exclusive Dish",
                "category_id": menu_category["id"],
                "price": "999.00",
            },
            headers=auth(admin_token)
        )
        resp_b = await client.get(
            "/api/v1/menu/items",
            headers=auth(admin_token_b)
        )
        names_b = [i["name"] for i in resp_b.json()]
        assert "Tenant A Exclusive Dish" not in names_b

    async def test_cannot_delete_category_with_items(
        self, client, admin_token, menu_category
    ):
        await client.post(
            "/api/v1/menu/items",
            json={
                "name": "Anchored Item",
                "category_id": menu_category["id"],
                "price": "200.00",
            },
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/menu/categories/{menu_category['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "items" in resp.json()["detail"].lower()