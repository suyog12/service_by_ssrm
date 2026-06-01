import pytest
from tests.conftest import TEST_BUSINESS, auth


class TestChangePasswordPositive:

    async def test_change_password_success(self, client, registered_tenant, db):
        """TC-PWD-001: Admin changes password successfully"""
        # Fresh login
        login = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        token = login.json()["access_token"]

        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": TEST_BUSINESS["admin_password"],
                  "new_password": "NewPass@456"},
            headers=auth(token)
        )
        assert resp.status_code == 200
        assert "changed" in resp.json()["message"].lower()

        # Restore original password for other tests
        from app.utils.password import hash_password
        await db.execute(
            "UPDATE core.users SET password_hash = $1 WHERE email = $2",
            hash_password(TEST_BUSINESS["admin_password"]),
            TEST_BUSINESS["admin_email"]
        )

    async def test_must_change_password_cleared(self, client, db, registered_tenant):
        """TC-PWD-001: must_change_password = FALSE after change"""
        from app.utils.password import hash_password
        # Set must_change_password = TRUE
        await db.execute(
            "UPDATE core.users SET must_change_password = TRUE WHERE email = $1",
            TEST_BUSINESS["admin_email"]
        )
        login = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        token = login.json()["access_token"]
        await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": TEST_BUSINESS["admin_password"],
                  "new_password": "NewPass@789"},
            headers=auth(token)
        )
        row = await db.fetchrow(
            "SELECT must_change_password FROM core.users WHERE email = $1",
            TEST_BUSINESS["admin_email"]
        )
        assert row["must_change_password"] is False
        # Restore
        await db.execute(
            "UPDATE core.users SET password_hash = $1 WHERE email = $2",
            hash_password(TEST_BUSINESS["admin_password"]),
            TEST_BUSINESS["admin_email"]
        )


class TestChangePasswordNegative:

    async def test_wrong_current_password(self, client, admin_token):
        """TC-PWD-003: Wrong current password returns 400"""
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "WrongCurrent!", "new_password": "NewPass@123"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "incorrect" in resp.json()["detail"].lower()

    async def test_missing_new_password(self, client, admin_token):
        """TC-PWD-004: Missing new_password returns 422"""
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": TEST_BUSINESS["admin_password"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_not_authenticated(self, client):
        """TC-PWD-005: No token returns 403"""
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "any", "new_password": "any"}
        )
        assert resp.status_code == 403


class TestChangePasswordSecurity:

    async def test_must_change_password_blocks_other_routes(self, client, db, registered_tenant):
        """TC-PWD-006: must_change_password=TRUE blocks all routes except change-password"""
        from app.utils.password import hash_password
        await db.execute(
            "UPDATE core.users SET must_change_password = TRUE WHERE email = $1",
            TEST_BUSINESS["admin_email"]
        )
        login = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        token = login.json()["access_token"]

        resp = await client.get("/api/v1/users/me", headers=auth(token))
        assert resp.status_code == 403
        assert "must change your password" in resp.json()["detail"].lower()

        # Restore
        await db.execute(
            "UPDATE core.users SET must_change_password = FALSE WHERE email = $1",
            TEST_BUSINESS["admin_email"]
        )