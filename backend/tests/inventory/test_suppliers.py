import pytest


def auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestSupplierPositive:
    async def test_admin_creates_supplier(self, client, admin_token):
        resp = await client.post(
            "/api/v1/inventory/suppliers",
            json={
                "name": "Ram Suppliers Pvt Ltd",
                "contact_person": "Ram Bahadur",
                "phone": "9800000010",
                "email": "ram@suppliers.com",
                "address": "Asan, Kathmandu",
                "pan_number": "302847999",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Ram Suppliers Pvt Ltd"
        assert data["is_active"] is True

    async def test_supplier_appears_in_list(self, client, admin_token, supplier):
        resp = await client.get(
            "/api/v1/inventory/suppliers",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        ids = [s["id"] for s in resp.json()]
        assert str(supplier["id"]) in ids

    async def test_get_single_supplier(self, client, admin_token, supplier):
        resp = await client.get(
            f"/api/v1/inventory/suppliers/{supplier['id']}",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == supplier["name"]

    async def test_update_supplier(self, client, admin_token, supplier):
        resp = await client.patch(
            f"/api/v1/inventory/suppliers/{supplier['id']}",
            json={"contact_person": "Shyam Bahadur"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["contact_person"] == "Shyam Bahadur"

    async def test_deactivate_supplier(self, client, admin_token, supplier):
        resp = await client.patch(
            f"/api/v1/inventory/suppliers/{supplier['id']}",
            json={"is_active": False},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_active_only_filter(self, client, admin_token, supplier):
        await client.patch(
            f"/api/v1/inventory/suppliers/{supplier['id']}",
            json={"is_active": False},
            headers=auth(admin_token),
        )
        resp = await client.get(
            "/api/v1/inventory/suppliers?active_only=true",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        ids = [s["id"] for s in resp.json()]
        assert str(supplier["id"]) not in ids

    async def test_staff_can_list_suppliers(self, client, staff_token):
        resp = await client.get(
            "/api/v1/inventory/suppliers",
            headers=auth(staff_token),
        )
        assert resp.status_code == 200


class TestSupplierNegative:
    async def test_duplicate_name_rejected(self, client, admin_token, supplier):
        resp = await client.post(
            "/api/v1/inventory/suppliers",
            json={"name": supplier["name"]},
            headers=auth(admin_token),
        )
        assert resp.status_code == 400

    async def test_empty_name_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/inventory/suppliers",
            json={"name": ""},
            headers=auth(admin_token),
        )
        assert resp.status_code == 422

    async def test_get_nonexistent_supplier(self, client, admin_token):
        resp = await client.get(
            "/api/v1/inventory/suppliers/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token),
        )
        assert resp.status_code == 404

    async def test_staff_cannot_create_supplier(self, client, staff_token):
        resp = await client.post(
            "/api/v1/inventory/suppliers",
            json={"name": "Unauthorized Supplier"},
            headers=auth(staff_token),
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_list(self, client):
        resp = await client.get("/api/v1/inventory/suppliers")
        assert resp.status_code == 403


@pytest.fixture
async def supplier(client, admin_token):
    resp = await client.post(
        "/api/v1/inventory/suppliers",
        json={"name": "Test Supplier Nepal", "phone": "9800000099"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    return resp.json()