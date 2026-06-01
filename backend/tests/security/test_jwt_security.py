import pytest
import base64
import json
from tests.conftest import auth, TEST_BUSINESS


class TestJWTSecurity:

    async def test_tampered_payload_rejected(self, client, admin_token):
        """TC-SEC-003: Tampered JWT is rejected"""
        parts = admin_token.split(".")
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        payload["is_super_admin"] = True
        fake = base64.b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        tampered = f"{parts[0]}.{fake}.{parts[2]}"
        resp = await client.get("/api/v1/auth/me", headers=auth(tampered))
        assert resp.status_code == 401

    async def test_refresh_token_rejected_as_access_token(self, client, admin_refresh_token):
        """Refresh token type check prevents it from being used as access"""
        resp = await client.get("/api/v1/auth/me", headers=auth(admin_refresh_token))
        assert resp.status_code == 401

    async def test_expired_token_format_rejected(self, client):
        """Completely fake token returns 401"""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.fake.fake"}
        )
        assert resp.status_code == 401