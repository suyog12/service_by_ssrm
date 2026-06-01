import pytest
from tests.conftest import auth


class TestOnboardingPositive:

    async def test_admin_completes_onboarding(self, client, admin_token):
        """TC-TEN-004: Admin marks onboarding complete"""
        resp = await client.post(
            "/api/v1/tenants/me/complete-onboarding",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

        profile = await client.get("/api/v1/tenants/me", headers=auth(admin_token))
        assert profile.json()["onboarding_complete"] is True

    async def test_onboarding_idempotent(self, client, admin_token):
        """TC-TEN-005: Calling twice does not error"""
        resp = await client.post(
            "/api/v1/tenants/me/complete-onboarding",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200


class TestOnboardingNegative:

    async def test_staff_cannot_complete_onboarding(self, client, staff_token):
        """TC-TEN-006: Staff cannot complete onboarding"""
        resp = await client.post(
            "/api/v1/tenants/me/complete-onboarding",
            headers=auth(staff_token)
        )
        assert resp.status_code == 403