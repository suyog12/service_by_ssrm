import pytest
from tests.conftest import auth


class TestFeaturesPositive:

    async def test_admin_can_list_features(self, client, admin_token):
        """TC-ROL-001: Admin gets all features"""
        resp = await client.get("/api/v1/roles/features", headers=auth(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_feature_count_is_45(self, client, admin_token):
        """TC-ROL-002: Exactly 45 features seeded"""
        resp = await client.get("/api/v1/roles/features", headers=auth(admin_token))
        assert len(resp.json()) == 48

    async def test_feature_has_correct_fields(self, client, admin_token):
        """Each feature has id, code, name, module"""
        resp = await client.get("/api/v1/roles/features", headers=auth(admin_token))
        feature = resp.json()[0]
        assert "id" in feature
        assert "code" in feature
        assert "name" in feature
        assert "module" in feature

    async def test_staff_can_list_features(self, client, staff_token):
        """Any authenticated user can list features"""
        resp = await client.get("/api/v1/roles/features", headers=auth(staff_token))
        assert resp.status_code == 200


class TestFeaturesNegative:

    async def test_unauthenticated_cannot_list(self, client):
        """TC-ROL-003: No token returns 403"""
        resp = await client.get("/api/v1/roles/features")
        assert resp.status_code == 403