import pytest
from tests.conftest import auth


class TestCategoryPositive:

    async def test_admin_creates_category(self, client, admin_token):
        """Admin can create a menu category"""
        resp = await client.post(
            "/api/v1/menu/categories",
            json={"name": "Main Course", "description": "Main dishes", "sort_order": 1},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Main Course"
        assert data["description"] == "Main dishes"
        assert data["sort_order"] == 1
        assert data["is_active"] is True
        assert "id" in data

    async def test_category_appears_in_list(self, client, admin_token):
        """Created category shows up in list"""
        resp = await client.get(
            "/api/v1/menu/categories",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "Main Course" in names

    async def test_create_category_minimal(self, client, admin_token):
        """Category with name only, no description"""
        resp = await client.post(
            "/api/v1/menu/categories",
            json={"name": "Beverages"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Beverages"
        assert resp.json()["description"] is None
        assert resp.json()["sort_order"] == 0

    async def test_update_category_name(self, client, admin_token):
        """Admin can update category name"""
        create = await client.post(
            "/api/v1/menu/categories",
            json={"name": "Starters"},
            headers=auth(admin_token)
        )
        cat_id = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/menu/categories/{cat_id}",
            json={"name": "Appetizers"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Appetizers"

    async def test_update_category_sort_order(self, client, admin_token):
        """Admin can update sort order"""
        create = await client.post(
            "/api/v1/menu/categories",
            json={"name": "Desserts"},
            headers=auth(admin_token)
        )
        cat_id = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/menu/categories/{cat_id}",
            json={"sort_order": 10},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["sort_order"] == 10

    async def test_deactivate_category(self, client, admin_token):
        """Admin can deactivate a category via update"""
        create = await client.post(
            "/api/v1/menu/categories",
            json={"name": "Specials"},
            headers=auth(admin_token)
        )
        cat_id = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/menu/categories/{cat_id}",
            json={"is_active": False},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_delete_empty_category(self, client, admin_token):
        """Admin can delete a category with no items"""
        create = await client.post(
            "/api/v1/menu/categories",
            json={"name": "ToDelete"},
            headers=auth(admin_token)
        )
        cat_id = create.json()["id"]
        resp = await client.delete(
            f"/api/v1/menu/categories/{cat_id}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()

    async def test_staff_can_list_categories(self, client, staff_token):
        """Any authenticated user can list categories"""
        resp = await client.get(
            "/api/v1/menu/categories",
            headers=auth(staff_token)
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestCategoryNegative:

    async def test_duplicate_name_rejected(self, client, admin_token):
        """Cannot create two categories with the same name"""
        await client.post(
            "/api/v1/menu/categories",
            json={"name": "Soups"},
            headers=auth(admin_token)
        )
        resp = await client.post(
            "/api/v1/menu/categories",
            json={"name": "Soups"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    async def test_empty_name_rejected(self, client, admin_token):
        """Empty name returns 422"""
        resp = await client.post(
            "/api/v1/menu/categories",
            json={"name": ""},
            headers=auth(admin_token)
        )
        assert resp.status_code in [400, 422]

    async def test_spaces_only_name_rejected(self, client, admin_token):
        """Whitespace-only name rejected"""
        resp = await client.post(
            "/api/v1/menu/categories",
            json={"name": "     "},
            headers=auth(admin_token)
        )
        assert resp.status_code in [400, 422]

    async def test_update_nonexistent_category(self, client, admin_token):
        """Update on non-existent ID returns 404"""
        resp = await client.patch(
            "/api/v1/menu/categories/00000000-0000-0000-0000-000000000000",
            json={"name": "Ghost"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_delete_nonexistent_category(self, client, admin_token):
        """Delete on non-existent ID returns 404"""
        resp = await client.delete(
            "/api/v1/menu/categories/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_staff_cannot_create_category(self, client, staff_token):
        """Staff without admin cannot create categories"""
        resp = await client.post(
            "/api/v1/menu/categories",
            json={"name": "HackerCategory"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_list(self, client):
        """No token returns 403"""
        resp = await client.get("/api/v1/menu/categories")
        assert resp.status_code == 403