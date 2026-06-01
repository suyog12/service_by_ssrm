import pytest
from tests.conftest import auth


class TestUserPermissionsPositive:

    async def test_permissions_for_user_with_role(self, client, admin_token, staff_user, manager_role):
        """TC-USR-020: User with role returns resolved permissions"""
        await client.post(
            "/api/v1/users/assign-role",
            json={"user_id": staff_user["user_id"], "role_template_id": manager_role["id"]},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/users/{staff_user['user_id']}/permissions",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        perms = resp.json()
        assert isinstance(perms, dict)
        assert len(perms) >= 1

    async def test_override_takes_precedence(self, client, admin_token, staff_user):
        """TC-USR-021: Override replaces role permission in resolved view"""
        await client.post(
            "/api/v1/users/permissions",
            json={"user_id": staff_user["user_id"],
                  "feature_code": "billing.void", "access_level": "edit"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/users/{staff_user['user_id']}/permissions",
            headers=auth(admin_token)
        )
        assert resp.json().get("billing.void") == "edit"

    async def test_deactivate_user(self, client, admin_token, db, registered_tenant):
        """TC-USR-017: Admin deactivates staff, login fails"""
        from app.utils.password import hash_password

        tenant = await db.fetchrow(
            "SELECT id FROM core.tenants WHERE schema_name = $1",
            registered_tenant["schema_name"]
        )
        assert tenant is not None

        user = await db.fetchrow(
            """
            INSERT INTO core.users
                (tenant_id, full_name, email, password_hash, is_admin,
                is_super_admin, must_change_password)
            VALUES ($1, 'To Deactivate', 'todeactivate@testhotel.com', $2, FALSE, FALSE, FALSE)
            RETURNING id
            """,
            tenant["id"],
            hash_password("TestPass@123")
        )
        schema = registered_tenant["schema_name"]
        await db.execute(
            f'INSERT INTO "{schema}".user_profiles (id, display_name) VALUES ($1, $2)',
            user["id"], "To Deactivate"
        )
        user_id = str(user["id"])

        deact = await client.patch(
            f"/api/v1/users/{user_id}/deactivate",
            headers=auth(admin_token)
        )
        assert deact.status_code == 200

        login = await client.post("/api/v1/auth/login", json={
            "email": "todeactivate@testhotel.com",
            "password": "TestPass@123",
            "tenant_slug": "test-hotel-nepal"
        })
        assert login.status_code == 401
        await db.execute("DELETE FROM core.users WHERE id = $1", user["id"])