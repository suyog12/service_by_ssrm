import pytest
from tests.conftest import TEST_BUSINESS, auth


class TestLogoutPositive:

    async def test_valid_logout_returns_200(self, client, registered_tenant):
        """TC-OUT-001: Valid logout returns success"""
        login = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        refresh_token = login.json()["refresh_token"]
        resp = await client.post("/api/v1/auth/logout", json={
            "refresh_token": refresh_token
        })
        assert resp.status_code == 200
        assert "Logged out" in resp.json()["message"]

    async def test_refresh_token_revoked_in_db(self, client, db, registered_tenant):
        """TC-OUT-002: Token is marked revoked in DB after logout"""
        login = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        refresh_token = login.json()["refresh_token"]
        await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})

        # Check DB
        tokens = await db.fetch(
            "SELECT revoked FROM core.refresh_tokens WHERE revoked = TRUE"
        )
        assert len(tokens) >= 1


class TestLogoutNegative:

    async def test_invalid_token_logout(self, client):
        """TC-OUT-003: Invalid token returns 400"""
        resp = await client.post("/api/v1/auth/logout", json={
            "refresh_token": "garbagetoken"
        })
        assert resp.status_code == 400


class TestLogoutSecurity:

    async def test_access_token_still_works_after_logout(self, client, registered_tenant):
        """TC-OUT-004: Access token is stateless — still works until expiry"""
        login = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        access_token = login.json()["access_token"]
        refresh_token = login.json()["refresh_token"]

        # Logout
        await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})

        # Access token still works — this is by design
        me_resp = await client.get("/api/v1/auth/me", headers=auth(access_token))
        assert me_resp.status_code == 200