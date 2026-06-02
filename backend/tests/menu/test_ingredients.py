import pytest
from tests.conftest import auth


@pytest.fixture
async def ingredient(client, admin_token):
    resp = await client.post(
        "/api/v1/ingredients",
        json={"name": "Chicken Breast", "unit": "grams", "reorder_level": "500"},
        headers=auth(admin_token)
    )
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        items = await client.get("/api/v1/ingredients", headers=auth(admin_token))
        for i in items.json():
            if i["name"] == "Chicken Breast":
                return i
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def menu_item(client, admin_token):
    cat = await client.post(
        "/api/v1/menu/categories",
        json={"name": "Ingredient Test Category"},
        headers=auth(admin_token)
    )
    if cat.status_code == 400:
        cats = await client.get("/api/v1/menu/categories", headers=auth(admin_token))
        cat_id = next(c["id"] for c in cats.json() if c["name"] == "Ingredient Test Category")
    else:
        cat_id = cat.json()["id"]

    resp = await client.post(
        "/api/v1/menu/items",
        json={"name": "Grilled Chicken", "category_id": cat_id, "price": "450.00"},
        headers=auth(admin_token)
    )
    if resp.status_code == 400:
        items = await client.get("/api/v1/menu/items", headers=auth(admin_token))
        return next(i for i in items.json() if i["name"] == "Grilled Chicken")
    assert resp.status_code == 201
    return resp.json()


class TestIngredientPositive:

    async def test_admin_creates_ingredient(self, client, admin_token):
        resp = await client.post(
            "/api/v1/ingredients",
            json={"name": "Tomato", "unit": "grams"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Tomato"
        assert data["unit"] == "grams"
        assert float(data["current_stock"]) == 0
        assert "id" in data

    async def test_ingredient_appears_in_list(self, client, admin_token, ingredient):
        resp = await client.get("/api/v1/ingredients", headers=auth(admin_token))
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()]
        assert ingredient["name"] in names

    async def test_get_single_ingredient(self, client, admin_token, ingredient):
        resp = await client.get(
            f"/api/v1/ingredients/{ingredient['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == ingredient["id"]

    async def test_update_ingredient(self, client, admin_token, ingredient):
        resp = await client.patch(
            f"/api/v1/ingredients/{ingredient['id']}",
            json={"reorder_level": "1000"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert float(resp.json()["reorder_level"]) == 1000

    async def test_staff_can_list_ingredients(self, client, staff_token):
        resp = await client.get("/api/v1/ingredients", headers=auth(staff_token))
        assert resp.status_code == 200

    async def test_delete_unlinked_ingredient(self, client, admin_token):
        create = await client.post(
            "/api/v1/ingredients",
            json={"name": "DeleteMe Ingredient", "unit": "kg"},
            headers=auth(admin_token)
        )
        assert create.status_code == 201
        iid = create.json()["id"]
        resp = await client.delete(
            f"/api/v1/ingredients/{iid}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200


class TestIngredientNegative:

    async def test_duplicate_name_rejected(self, client, admin_token, ingredient):
        resp = await client.post(
            "/api/v1/ingredients",
            json={"name": ingredient["name"], "unit": "kg"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    async def test_empty_name_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/ingredients",
            json={"name": "", "unit": "grams"},
            headers=auth(admin_token)
        )
        assert resp.status_code in [400, 422]

    async def test_get_nonexistent_ingredient(self, client, admin_token):
        resp = await client.get(
            "/api/v1/ingredients/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_staff_cannot_create_ingredient(self, client, staff_token):
        resp = await client.post(
            "/api/v1/ingredients",
            json={"name": "Unauthorized Ingredient", "unit": "grams"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_cannot_delete_linked_ingredient(
        self, client, admin_token, ingredient, menu_item
    ):
        await client.post(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients",
            json={"ingredient_id": ingredient["id"], "quantity_used": "150"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/ingredients/{ingredient['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "linked" in resp.json()["detail"].lower()


class TestItemIngredientLinking:

    async def test_add_ingredient_to_item(self, client, admin_token, ingredient, menu_item):
        resp = await client.post(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients",
            json={"ingredient_id": ingredient["id"], "quantity_used": "200"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ingredient_id"] == ingredient["id"]
        assert float(data["quantity_used"]) == 200
        assert data["ingredient_name"] == ingredient["name"]
        assert data["unit"] == ingredient["unit"]

    async def test_ingredient_appears_in_item_list(
        self, client, admin_token, ingredient, menu_item
    ):
        await client.post(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients",
            json={"ingredient_id": ingredient["id"], "quantity_used": "200"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        ids = [i["ingredient_id"] for i in resp.json()]
        assert ingredient["id"] in ids

    async def test_update_quantity_used(self, client, admin_token, ingredient, menu_item):
        await client.post(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients",
            json={"ingredient_id": ingredient["id"], "quantity_used": "100"},
            headers=auth(admin_token)
        )
        resp = await client.patch(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients/{ingredient['id']}",
            json={"quantity_used": "250"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert float(resp.json()["quantity_used"]) == 250

    async def test_remove_ingredient_from_item(
        self, client, admin_token, ingredient, menu_item
    ):
        await client.post(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients",
            json={"ingredient_id": ingredient["id"], "quantity_used": "100"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients/{ingredient['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_duplicate_link_rejected(self, client, admin_token, ingredient, menu_item):
        await client.post(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients",
            json={"ingredient_id": ingredient["id"], "quantity_used": "100"},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients",
            json={"ingredient_id": ingredient["id"], "quantity_used": "50"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "already linked" in resp.json()["detail"].lower()

    async def test_zero_quantity_rejected(self, client, admin_token, ingredient, menu_item):
        resp = await client.post(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients",
            json={"ingredient_id": ingredient["id"], "quantity_used": "0"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_nonexistent_item_returns_404(self, client, admin_token, ingredient):
        resp = await client.post(
            "/api/v1/menu/items/00000000-0000-0000-0000-000000000000/ingredients",
            json={"ingredient_id": ingredient["id"], "quantity_used": "100"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_staff_can_list_item_ingredients(
        self, client, staff_token, admin_token, ingredient, menu_item
    ):
        await client.post(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients",
            json={"ingredient_id": ingredient["id"], "quantity_used": "100"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/menu/items/{menu_item['id']}/ingredients",
            headers=auth(staff_token)
        )
        assert resp.status_code == 200