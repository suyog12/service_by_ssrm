import pytest
from tests.conftest import auth


class TestTenantProfilePositive:

    async def test_admin_gets_tenant_profile(self, client, admin_token):
        """TC-TEN-001: Admin gets tenant profile"""
        resp = await client.get("/api/v1/tenants/me", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "name" in data
        assert "schema_name" in data
        assert data["schema_name"] == "tenant_test_hotel_nepal"
        assert data["subscription_tier"] == "ez"


class TestTenantProfileNegative:

    async def test_staff_cannot_get_tenant_profile(self, client, staff_token):
        """TC-TEN-002: Staff returns 403"""
        resp = await client.get("/api/v1/tenants/me", headers=auth(staff_token))
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_get_profile(self, client):
        """TC-TEN-003: No token returns 403"""
        resp = await client.get("/api/v1/tenants/me")
        assert resp.status_code == 403