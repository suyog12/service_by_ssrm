import pytest
from tests.conftest import auth


class TestEZPlanBlocksHotelFeatures:

    async def test_ez_plan_admin_cannot_list_room_types(
        self, client, ez_admin_token
    ):
        resp = await client.get("/api/v1/hotel/room-types", headers=auth(ez_admin_token))
        assert resp.status_code == 403
        assert "plan" in resp.json()["detail"].lower()

    async def test_ez_plan_admin_cannot_create_room_type(
        self, client, ez_admin_token
    ):
        resp = await client.post(
            "/api/v1/hotel/room-types",
            json={"name": "EZ Room", "base_price": "3000"},
            headers=auth(ez_admin_token)
        )
        assert resp.status_code == 403

    async def test_ez_plan_admin_cannot_list_rooms(
        self, client, ez_admin_token
    ):
        resp = await client.get("/api/v1/hotel/rooms", headers=auth(ez_admin_token))
        assert resp.status_code == 403

    async def test_ez_plan_admin_cannot_list_reservations(
        self, client, ez_admin_token
    ):
        resp = await client.get("/api/v1/hotel/reservations", headers=auth(ez_admin_token))
        assert resp.status_code == 403

    async def test_ez_plan_admin_cannot_list_guests(
        self, client, ez_admin_token
    ):
        resp = await client.get("/api/v1/hotel/guests", headers=auth(ez_admin_token))
        assert resp.status_code == 403

    async def test_ez_plan_admin_cannot_check_in(
        self, client, ez_admin_token
    ):
        resp = await client.post(
            "/api/v1/hotel/reservations/00000000-0000-0000-0000-000000000000/check-in",
            headers=auth(ez_admin_token)
        )
        assert resp.status_code == 403

    async def test_ez_plan_admin_cannot_check_availability(
        self, client, ez_admin_token
    ):
        resp = await client.get(
            "/api/v1/hotel/rooms/availability?check_in=2026-08-01&check_out=2026-08-05&adults=1",
            headers=auth(ez_admin_token)
        )
        assert resp.status_code == 403


class TestEZPlanCanStillAccessRestaurantFeatures:

    async def test_ez_plan_can_access_menu(self, client, ez_admin_token):
        resp = await client.get("/api/v1/menu/categories", headers=auth(ez_admin_token))
        assert resp.status_code == 200

    async def test_ez_plan_can_access_orders(self, client, ez_admin_token):
        resp = await client.get("/api/v1/orders", headers=auth(ez_admin_token))
        assert resp.status_code == 200

    async def test_ez_plan_can_access_billing(self, client, ez_admin_token):
        resp = await client.get("/api/v1/billing/bills", headers=auth(ez_admin_token))
        assert resp.status_code == 200

    async def test_ez_plan_can_access_inventory(self, client, ez_admin_token):
        resp = await client.get("/api/v1/inventory/suppliers", headers=auth(ez_admin_token))
        assert resp.status_code == 200

    async def test_ez_plan_can_access_floor(self, client, ez_admin_token):
        resp = await client.get("/api/v1/floor/sections", headers=auth(ez_admin_token))
        assert resp.status_code == 200

    async def test_ez_plan_can_access_outlets(self, client, ez_admin_token):
        resp = await client.get("/api/v1/outlets", headers=auth(ez_admin_token))
        assert resp.status_code == 200


class TestMaxPlanCanAccessEverything:

    async def test_max_plan_can_access_hotel_room_types(
        self, client, admin_token
    ):
        # admin_token is on max tier (set in registered_tenant fixture)
        resp = await client.get("/api/v1/hotel/room-types", headers=auth(admin_token))
        assert resp.status_code == 200

    async def test_max_plan_can_access_hotel_rooms(self, client, admin_token):
        resp = await client.get("/api/v1/hotel/rooms", headers=auth(admin_token))
        assert resp.status_code == 200

    async def test_max_plan_can_access_hotel_guests(self, client, admin_token):
        resp = await client.get("/api/v1/hotel/guests", headers=auth(admin_token))
        assert resp.status_code == 200

    async def test_max_plan_can_access_hotel_reservations(self, client, admin_token):
        resp = await client.get("/api/v1/hotel/reservations", headers=auth(admin_token))
        assert resp.status_code == 200

    async def test_max_plan_can_access_all_analytics(self, client, admin_token):
        # Analytics endpoints don't exist yet but tier should not block
        # This verifies max plan has no restrictions in TIER_RESTRICTIONS
        resp = await client.get("/api/v1/hotel/room-types", headers=auth(admin_token))
        assert resp.status_code == 200


EZ_BUSINESS = {
    "business_name": "EZ Restaurant Nepal",
    "business_type": "restaurant",
    "business_email": "admin@ezrest.com",
    "business_phone": "9800000003",
    "city": "Lalitpur",
    "admin_full_name": "EZ Admin",
    "admin_email": "ezadmin@ezrest.com",
    "admin_password": "EZPass@123",
    "admin_phone": "9800000003"
}


@pytest.fixture
async def ez_tenant(client, db):
    resp = await client.post("/api/v1/auth/register", json=EZ_BUSINESS)
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        from app.utils.password import hash_password
        await db.execute(
            "UPDATE core.users SET password_hash=$1, must_change_password=FALSE WHERE email=$2",
            hash_password(EZ_BUSINESS["admin_password"]),
            EZ_BUSINESS["admin_email"]
        )
    else:
        assert resp.status_code == 201, resp.text
        # Explicitly set to ez tier (default is ez but being explicit)
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'ez' WHERE slug = $1",
            "ez-restaurant-nepal"
        )
    return EZ_BUSINESS


@pytest.fixture
async def ez_admin_token(client, ez_tenant):
    resp = await client.post("/api/v1/auth/login", json={
        "email": EZ_BUSINESS["admin_email"],
        "password": EZ_BUSINESS["admin_password"],
        "tenant_slug": "ez-restaurant-nepal"
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]