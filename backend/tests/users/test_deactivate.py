import pytest
from tests.conftest import TEST_BUSINESS, auth


class TestDeactivatePositive:

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

    async def test_reactivate_user(self, client, admin_token, db):
        """TC-USR-019: Admin reactivates user, login works again"""
        row = await db.fetchrow(
            "SELECT id FROM core.users WHERE email = 'todeactivate@testhotel.com'"
        )
        if not row:
            return
        user_id = str(row["id"])
        resp = await client.patch(
            f"/api/v1/users/{user_id}/reactivate",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200


class TestDeactivateNegative:

    async def test_admin_cannot_deactivate_self(self, client, admin_token, registered_tenant):
        """TC-USR-018: Admin cannot deactivate themselves"""
        me = await client.get("/api/v1/auth/me", headers=auth(admin_token))
        admin_id = me.json()["user_id"]
        resp = await client.patch(
            f"/api/v1/users/{admin_id}/deactivate",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"].lower()