import pytest
from tests.conftest import auth


class TestMePositive:

    async def test_authenticated_user_gets_data(self, client, admin_token):
        """TC-ME-001: Authenticated user gets their data"""
        resp = await client.get("/api/v1/auth/me", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data
        assert "tenant_id" in data
        assert "schema_name" in data
        assert data["is_admin"] is True

    async def test_schema_name_in_response(self, client, admin_token):
        """Schema name matches expected tenant"""
        resp = await client.get("/api/v1/auth/me", headers=auth(admin_token))
        assert resp.json()["schema_name"] == "tenant_test_hotel_nepal"


class TestMeNegative:

    async def test_no_token_returns_403(self, client):
        """TC-ME-002: No token returns 403"""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 403

    async def test_malformed_token_returns_401(self, client):
        """TC-ME-003: Malformed token returns 401"""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer thisisnotavalidtoken"}
        )
        assert resp.status_code == 401

    async def test_empty_bearer_returns_403(self, client):
        """Empty bearer string"""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer "}
        )
        assert resp.status_code in [401, 403]


class TestMeSecurity:

    async def test_refresh_token_rejected_on_me(self, client, admin_refresh_token):
        """TC-ME-005: Refresh token cannot be used on /me"""
        resp = await client.get(
            "/api/v1/auth/me",
            headers=auth(admin_refresh_token)
        )
        assert resp.status_code == 401

    async def test_tampered_token_rejected(self, client, admin_token):
        """TC-ME-004: Tampered JWT payload rejected"""
        import base64, json
        parts = admin_token.split(".")
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        payload["is_admin"] = True
        payload["is_super_admin"] = True
        fake_payload = base64.b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip("=")
        tampered = f"{parts[0]}.{fake_payload}.{parts[2]}"
        resp = await client.get("/api/v1/auth/me", headers=auth(tampered))
        assert resp.status_code == 401