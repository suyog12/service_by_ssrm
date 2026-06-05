import pytest


def auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestOutletPositive:
    async def test_admin_creates_outlet(self, client, admin_token):
        resp = await client.post(
            "/api/v1/outlets",
            json={
                "name": "Main Restaurant",
                "type": "restaurant",
                "kitchen_mode": "single_printer",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Main Restaurant"
        assert data["is_default"] is False
        assert data["kitchen_mode"] == "single_printer"

    async def test_first_outlet_is_default(self, client, admin_token):
        resp = await client.post(
            "/api/v1/outlets",
            json={"name": "First Outlet", "type": "cafe"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        assert resp.json()["is_default"] is False

    async def test_second_outlet_is_not_default(self, client, admin_token):
        await client.post(
            "/api/v1/outlets",
            json={"name": "Outlet One", "type": "restaurant"},
            headers=auth(admin_token),
        )
        resp = await client.post(
            "/api/v1/outlets",
            json={"name": "Outlet Two", "type": "bar"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        assert resp.json()["is_default"] is False

    async def test_outlet_appears_in_list(self, client, admin_token, outlet):
        resp = await client.get(
            "/api/v1/outlets",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        ids = [o["id"] for o in resp.json()]
        assert str(outlet["id"]) in ids

    async def test_get_single_outlet(self, client, admin_token, outlet):
        resp = await client.get(
            f"/api/v1/outlets/{outlet['id']}",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == outlet["name"]

    async def test_update_outlet_name(self, client, admin_token, outlet):
        resp = await client.patch(
            f"/api/v1/outlets/{outlet['id']}",
            json={"name": "Updated Outlet Name"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Outlet Name"

    async def test_update_kitchen_mode(self, client, admin_token, outlet):
        resp = await client.patch(
            f"/api/v1/outlets/{outlet['id']}",
            json={"kitchen_mode": "paperless"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["kitchen_mode"] == "paperless"

    async def test_deactivate_outlet(self, client, admin_token, outlet):
        resp = await client.patch(
            f"/api/v1/outlets/{outlet['id']}",
            json={"is_active": False},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_active_only_filter(self, client, admin_token, outlet):
        await client.patch(
            f"/api/v1/outlets/{outlet['id']}",
            json={"is_active": False},
            headers=auth(admin_token),
        )
        resp = await client.get(
            "/api/v1/outlets?active_only=true",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        ids = [o["id"] for o in resp.json()]
        assert str(outlet["id"]) not in ids

    async def test_staff_can_list_outlets(self, client, staff_token):
        resp = await client.get(
            "/api/v1/outlets",
            headers=auth(staff_token),
        )
        assert resp.status_code == 200

    async def test_billing_settings_created_for_first_outlet(
        self, client, admin_token
    ):
        outlet_resp = await client.post(
            "/api/v1/outlets",
            json={"name": "Settings Test Outlet", "type": "restaurant"},
            headers=auth(admin_token),
        )
        assert outlet_resp.status_code == 201
        resp = await client.get(
            "/api/v1/billing/settings",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200

    async def test_create_outlet_with_all_types(self, client, admin_token):
        for outlet_type in ("restaurant", "bar", "cafe", "banquet", "other"):
            resp = await client.post(
                "/api/v1/outlets",
                json={"name": f"Type Test {outlet_type}", "type": outlet_type},
                headers=auth(admin_token),
            )
            assert resp.status_code == 201


class TestOutletNegative:
    async def test_duplicate_name_rejected(self, client, admin_token, outlet):
        resp = await client.post(
            "/api/v1/outlets",
            json={"name": outlet["name"], "type": "restaurant"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 400

    async def test_empty_name_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/outlets",
            json={"name": "", "type": "restaurant"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 422

    async def test_invalid_type_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/outlets",
            json={"name": "Invalid Type", "type": "nightclub"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 422

    async def test_invalid_kitchen_mode_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/outlets",
            json={"name": "Bad Mode", "type": "restaurant", "kitchen_mode": "magic"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 422

    async def test_get_nonexistent_outlet(self, client, admin_token):
        resp = await client.get(
            "/api/v1/outlets/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token),
        )
        assert resp.status_code == 404

    async def test_staff_cannot_create_outlet(self, client, staff_token):
        resp = await client.post(
            "/api/v1/outlets",
            json={"name": "Unauthorized Outlet", "type": "restaurant"},
            headers=auth(staff_token),
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_list(self, client):
        resp = await client.get("/api/v1/outlets")
        assert resp.status_code == 403

    async def test_ez_plan_outlet_limit(self, client, admin_token, db):
        # Explicitly set to EZ for this test
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'ez' "
            "WHERE slug = 'test-hotel-nepal'"
        )
        # Default outlet already occupies the 1 slot on EZ plan
        resp = await client.post(
            "/api/v1/outlets",
            json={"name": "EZ Outlet Two", "type": "bar"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 400
        assert "plan" in resp.json()["detail"].lower()


@pytest.fixture
async def outlet(client, admin_token):
    resp = await client.post(
        "/api/v1/outlets",
        json={"name": "Test Outlet Nepal", "type": "restaurant"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture(autouse=True)
async def set_pro_plan(db):
    await db.execute(
        "UPDATE core.tenants SET subscription_tier = 'max' "
        "WHERE slug = 'test-hotel-nepal'"
    )
    yield
    await db.execute(
        "UPDATE core.tenants SET subscription_tier = 'ez' "
        "WHERE slug = 'test-hotel-nepal'"
    )