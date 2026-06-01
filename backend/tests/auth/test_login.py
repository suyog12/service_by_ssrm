import pytest
from tests.conftest import TEST_BUSINESS, auth


class TestLoginPositive:

    async def test_valid_login_returns_tokens(self, client, registered_tenant):
        """TC-LOG-001: Valid login returns all expected fields"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["is_admin"] is True
        assert "must_change_password" in body

    async def test_login_returns_correct_schema_name(self, client, registered_tenant):
        """TC-LOG-002: Login response contains correct schema_name"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        assert resp.status_code == 200
        assert resp.json()["schema_name"] == "tenant_test_hotel_nepal"

    async def test_login_updates_last_login_at(self, client, db, registered_tenant):
        """Login updates last_login_at in core.users"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        assert resp.status_code == 200
        user_id = resp.json()["user_id"]
        row = await db.fetchrow(
            "SELECT last_login_at FROM core.users WHERE id = $1", user_id
        )
        assert row["last_login_at"] is not None


class TestLoginNegative:

    async def test_wrong_password(self, client, registered_tenant):
        """TC-LOG-003: Wrong password returns 401"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": "WrongPassword123",
            "tenant_slug": "test-hotel-nepal"
        })
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["detail"]

    async def test_wrong_email(self, client, registered_tenant):
        """TC-LOG-004: Wrong email returns 401"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@testhotel.com",
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["detail"]

    async def test_wrong_tenant_slug(self, client):
        """TC-LOG-005: Wrong tenant_slug returns 401"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "does-not-exist"
        })
        assert resp.status_code == 401
        assert "Business not found" in resp.json()["detail"]

    async def test_missing_tenant_slug(self, client):
        """TC-LOG-006: Missing tenant_slug returns 422"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
        })
        assert resp.status_code == 422

    async def test_deactivated_user_cannot_login(self, client, db, registered_tenant):
        """TC-LOG-007: Deactivated user gets 401"""
        from app.utils.password import hash_password

        # Get the actual tenant_id from DB using schema_name
        tenant = await db.fetchrow(
            "SELECT id FROM core.tenants WHERE schema_name = $1",
            registered_tenant["schema_name"]
        )
        assert tenant is not None, "Tenant not found"

        user = await db.fetchrow(
            """
            INSERT INTO core.users
                (tenant_id, full_name, email, password_hash, is_admin, is_active,
                is_super_admin, must_change_password)
            VALUES ($1, 'Deactivated User', 'deactivated@testhotel.com', $2, FALSE, FALSE, FALSE, FALSE)
            RETURNING id
            """,
            tenant["id"],
            hash_password("TestPass@123")
        )
        resp = await client.post("/api/v1/auth/login", json={
            "email": "deactivated@testhotel.com",
            "password": "TestPass@123",
            "tenant_slug": "test-hotel-nepal"
        })
        assert resp.status_code == 401
        assert "deactivated" in resp.json()["detail"]
        await db.execute("DELETE FROM core.users WHERE id = $1", user["id"])
        
    async def test_error_message_same_for_wrong_email_and_password(self, client, registered_tenant):
        """Security: error message does not reveal which field is wrong"""
        resp_bad_email = await client.post("/api/v1/auth/login", json={
            "email": "nobody@testhotel.com",
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        resp_bad_pass = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": "WrongPass123",
            "tenant_slug": "test-hotel-nepal"
        })
        assert resp_bad_email.json()["detail"] == resp_bad_pass.json()["detail"]


class TestLoginSecurity:

    async def test_sql_injection_in_email(self, client, registered_tenant):
        """TC-LOG-009: SQL injection in email field is rejected"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": "' OR '1'='1'--@test.com",
            "password": "anything",
            "tenant_slug": "test-hotel-nepal"
        })
        assert resp.status_code in [401, 422]

    async def test_brute_force_ten_attempts(self, client, registered_tenant):
        """TC-LOG-008: 10 rapid wrong attempts all return 401"""
        for _ in range(10):
            resp = await client.post("/api/v1/auth/login", json={
                "email": TEST_BUSINESS["admin_email"],
                "password": "WrongPassword!",
                "tenant_slug": "test-hotel-nepal"
            })
            assert resp.status_code == 401

    async def test_jwt_contains_required_claims(self, client, registered_tenant):
        """TC-LOG-010: JWT token contains all required claims"""
        import base64
        import json
        resp = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        token = resp.json()["access_token"]
        payload_b64 = token.split(".")[1]
        # Add padding
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        assert "user_id" in payload
        assert "tenant_id" in payload
        assert "schema_name" in payload
        assert "is_admin" in payload
        assert "exp" in payload
        assert payload["type"] == "access"