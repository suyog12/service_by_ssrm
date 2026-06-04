import pytest
from tests.conftest import auth


class TestBillingSettingsPositive:

    async def test_get_default_settings(self, client, admin_token):
        resp = await client.get(
            "/api/v1/billing/settings",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["vat_mode"] == "exclusive"
        assert float(data["vat_pct"]) == 13.00
        assert data["service_charge_mode"] == "exclusive"
        assert data["qr_type"] == "none"

    async def test_update_vat_mode_to_inclusive(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/billing/settings",
            json={"vat_mode": "inclusive"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["vat_mode"] == "inclusive"

    async def test_update_service_charge(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/billing/settings",
            json={"service_charge_pct": "10.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert float(resp.json()["service_charge_pct"]) == 10.00

    async def test_set_custom_qr(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/billing/settings",
            json={"qr_type": "custom", "qr_image_url": "https://example.com/qr.png"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["qr_type"] == "custom"
        assert resp.json()["qr_image_url"] == "https://example.com/qr.png"

    async def test_set_fonepay_shows_pending(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/billing/settings",
            json={"qr_type": "fonepay"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["qr_type"] == "fonepay"


class TestBillingSettingsNegative:

    async def test_invalid_vat_mode_rejected(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/billing/settings",
            json={"vat_mode": "magic"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_invalid_qr_type_rejected(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/billing/settings",
            json={"qr_type": "stripe"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_staff_cannot_update_settings(self, client, staff_token):
        resp = await client.patch(
            "/api/v1/billing/settings",
            json={"vat_mode": "inclusive"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403