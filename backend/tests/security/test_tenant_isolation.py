import pytest
from tests.conftest import auth


class TestTenantIsolation:

    async def test_tenant_a_cannot_see_tenant_b_users(self, client, admin_token, admin_token_b):
        """TC-SEC-001: Tenant A user list does not include Tenant B users"""
        resp_a = await client.get("/api/v1/users", headers=auth(admin_token))
        resp_b = await client.get("/api/v1/users", headers=auth(admin_token_b))
        emails_a = {u["email"] for u in resp_a.json()}
        emails_b = {u["email"] for u in resp_b.json()}
        assert emails_a.isdisjoint(emails_b)

    async def test_tenant_a_role_not_usable_in_tenant_b(self, client, admin_token, admin_token_b, manager_role, staff_user):
        """TC-SEC-002: Tenant A role ID rejected in Tenant B"""
        resp = await client.post(
            "/api/v1/users/assign-role",
            json={
                "user_id": staff_user["user_id"],
                "role_template_id": manager_role["id"]
            },
            headers=auth(admin_token_b)
        )
        assert resp.status_code in [400, 404]

    async def test_all_protected_routes_require_token(self, client):
        """TC-SEC-004: All protected routes return 403 without token"""
        routes = [
            ("GET", "/api/v1/users"),
            ("GET", "/api/v1/users/me"),
            ("GET", "/api/v1/roles"),
            ("GET", "/api/v1/tenants/me"),
        ]
        for method, route in routes:
            if method == "GET":
                resp = await client.get(route)
            assert resp.status_code == 403, f"{route} should return 403 without token"