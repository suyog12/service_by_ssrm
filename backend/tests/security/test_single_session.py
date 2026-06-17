import pytest
from tests.conftest import auth


class TestSingleSessionEnforcement:

    async def test_new_login_revokes_old_refresh_token(
        self, client, registered_tenant
    ):
        from tests.conftest import TEST_BUSINESS

        # First login
        login1 = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        assert login1.status_code == 200
        old_refresh = login1.json()["refresh_token"]

        # Second login — revokes first session
        login2 = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        assert login2.status_code == 200

        # Old refresh token should now be rejected
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh}
        )
        assert resp.status_code == 401

    async def test_new_login_issues_working_new_refresh_token(
        self, client, registered_tenant
    ):
        from tests.conftest import TEST_BUSINESS

        # First login
        await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })

        # Second login
        login2 = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        assert login2.status_code == 200
        new_refresh = login2.json()["refresh_token"]

        # New refresh token works
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": new_refresh}
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_old_access_token_still_works_after_new_login(
        self, client, registered_tenant
    ):
        """
        Access tokens are stateless JWTs — they remain valid until expiry
        even after a new login. Only refresh tokens are revoked.
        """
        from tests.conftest import TEST_BUSINESS

        login1 = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        old_access = login1.json()["access_token"]

        # New login
        await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })

        # Old access token still valid for its lifetime
        resp = await client.get("/api/v1/auth/me", headers=auth(old_access))
        assert resp.status_code == 200

    async def test_multiple_logins_all_previous_sessions_revoked(
        self, client, registered_tenant
    ):
        from tests.conftest import TEST_BUSINESS

        # Login three times
        logins = []
        for _ in range(3):
            resp = await client.post("/api/v1/auth/login", json={
                "email": TEST_BUSINESS["admin_email"],
                "password": TEST_BUSINESS["admin_password"],
                "tenant_slug": "test-hotel-nepal"
            })
            assert resp.status_code == 200
            logins.append(resp.json()["refresh_token"])

        # Only the last refresh token should work
        for old_token in logins[:-1]:
            resp = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": old_token}
            )
            assert resp.status_code == 401

        # Last token still works
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": logins[-1]}
        )
        assert resp.status_code == 200

    async def test_logout_then_new_login_works(
        self, client, registered_tenant
    ):
        from tests.conftest import TEST_BUSINESS

        login1 = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        refresh1 = login1.json()["refresh_token"]

        # Logout
        await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh1}
        )

        # Login again
        login2 = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        assert login2.status_code == 200
        assert "access_token" in login2.json()

    async def test_deactivated_user_session_rejected(
        self, client, admin_token, registered_tenant, db
    ):
        from tests.conftest import TEST_BUSINESS

        # Create a staff user
        create = await client.post(
            "/api/v1/users",
            json={"full_name": "Session Test User", "email": "sessiontest@test.com"},
            headers=auth(admin_token)
        )
        assert create.status_code == 201
        user_id = create.json()["user_id"]

        from app.utils.password import hash_password
        await db.execute(
            "UPDATE core.users SET password_hash=$1, must_change_password=FALSE WHERE id=$2",
            hash_password("Session@123"), user_id
        )

        # Login as staff
        login = await client.post("/api/v1/auth/login", json={
            "email": "sessiontest@test.com",
            "password": "Session@123",
            "tenant_slug": "test-hotel-nepal"
        })
        assert login.status_code == 200
        staff_access = login.json()["access_token"]

        # Admin deactivates the user
        await client.patch(
            f"/api/v1/users/{user_id}/deactivate",
            headers=auth(admin_token)
        )

        # Old access token now rejected (user deactivated check is in get_current_user)
        resp = await client.get("/api/v1/auth/me", headers=auth(staff_access))
        assert resp.status_code == 401
        
    async def test_debug_revocation(self, client, registered_tenant, db):
        from tests.conftest import TEST_BUSINESS

        login1 = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        old_refresh = login1.json()["refresh_token"]

        login2 = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })

        # Check what's in the DB
        rows = await db.fetch(
            "SELECT id, revoked, expires_at FROM core.refresh_tokens ORDER BY created_at"
        )
        for row in rows:
            print(f"token id={row['id']} revoked={row['revoked']}")

        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        print(f"refresh response: {resp.status_code} {resp.text}")
        
    async def test_debug_revocation(self, client, registered_tenant, db):
        from tests.conftest import TEST_BUSINESS

        login1 = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        old_refresh = login1.json()["refresh_token"]

        login2 = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })

        rows = await db.fetch(
            "SELECT id, revoked, expires_at FROM core.refresh_tokens ORDER BY created_at"
        )
        for row in rows:
            print(f"token id={row['id']} revoked={row['revoked']}")

        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        print(f"refresh response: {resp.status_code} {resp.text}")

    async def test_debug_verify(self, client, registered_tenant, db):
        from tests.conftest import TEST_BUSINESS
        from app.utils.password import verify_token

        login1 = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        old_refresh = login1.json()["refresh_token"]

        login2 = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        new_refresh = login2.json()["refresh_token"]

        print(f"\nold == new: {old_refresh == new_refresh}")
        print(f"old token: {old_refresh[:50]}")
        print(f"new token: {new_refresh[:50]}")

        rows = await db.fetch(
            "SELECT id, token_hash, revoked FROM core.refresh_tokens ORDER BY created_at"
        )
        for row in rows:
            old_matches = verify_token(old_refresh, row["token_hash"])
            new_matches = verify_token(new_refresh, row["token_hash"])
            print(f"id={str(row['id'])[:8]} revoked={row['revoked']} old_matches={old_matches} new_matches={new_matches}")