import pytest
from tests.conftest import auth


class TestPermissionOverridePositive:

    async def test_override_permission(self, client, admin_token, staff_user, manager_role):
        """TC-ROL-017: Override one permission for specific user"""
        resp = await client.post(
            "/api/v1/users/permissions",
            json={
                "user_id": staff_user["user_id"],
                "feature_code": "billing.void",
                "access_level": "edit"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_override_takes_precedence(self, client, admin_token, staff_user):
        """TC-ROL-018: Override appears in resolved permissions"""
        resp = await client.get(
            f"/api/v1/users/{staff_user['user_id']}/permissions",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        perms = resp.json()
        assert perms.get("billing.void") == "edit"

    async def test_override_is_idempotent(self, client, admin_token, staff_user):
        """Calling override twice with same value does not error"""
        for _ in range(2):
            resp = await client.post(
                "/api/v1/users/permissions",
                json={
                    "user_id": staff_user["user_id"],
                    "feature_code": "billing.void",
                    "access_level": "edit"
                },
                headers=auth(admin_token)
            )
            assert resp.status_code == 200


class TestPermissionOverrideNegative:

    async def test_invalid_feature_code(self, client, admin_token, staff_user):
        """TC-ROL-019: Invalid feature_code rejected"""
        resp = await client.post(
            "/api/v1/users/permissions",
            json={
                "user_id": staff_user["user_id"],
                "feature_code": "fake.nonexistent",
                "access_level": "edit"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code in [400, 422]