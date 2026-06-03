import pytest
from tests.conftest import auth


class TestSectionPositive:

    async def test_admin_creates_section(self, client, admin_token):
        resp = await client.post(
            "/api/v1/floor/sections",
            json={"name": "Indoor"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Indoor"
        assert data["is_active"] is True
        assert "id" in data

    async def test_section_appears_in_list(self, client, admin_token):
        await client.post(
            "/api/v1/floor/sections",
            json={"name": "Outdoor"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/floor/sections",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()]
        assert "Outdoor" in names

    async def test_update_section_name(self, client, admin_token):
        create = await client.post(
            "/api/v1/floor/sections",
            json={"name": "Terrace"},
            headers=auth(admin_token)
        )
        sid = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/floor/sections/{sid}",
            json={"name": "Rooftop Terrace"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Rooftop Terrace"

    async def test_deactivate_section(self, client, admin_token):
        create = await client.post(
            "/api/v1/floor/sections",
            json={"name": "Bar Area"},
            headers=auth(admin_token)
        )
        sid = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/floor/sections/{sid}",
            json={"is_active": False},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_delete_empty_section(self, client, admin_token):
        create = await client.post(
            "/api/v1/floor/sections",
            json={"name": "DeleteMe Section"},
            headers=auth(admin_token)
        )
        sid = create.json()["id"]
        resp = await client.delete(
            f"/api/v1/floor/sections/{sid}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_staff_can_list_sections(self, client, staff_token):
        resp = await client.get(
            "/api/v1/floor/sections",
            headers=auth(staff_token)
        )
        assert resp.status_code == 200


class TestSectionNegative:

    async def test_duplicate_name_rejected(self, client, admin_token):
        await client.post(
            "/api/v1/floor/sections",
            json={"name": "VIP Lounge"},
            headers=auth(admin_token)
        )
        resp = await client.post(
            "/api/v1/floor/sections",
            json={"name": "VIP Lounge"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    async def test_empty_name_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/floor/sections",
            json={"name": ""},
            headers=auth(admin_token)
        )
        assert resp.status_code in [400, 422]

    async def test_update_nonexistent_section(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/floor/sections/00000000-0000-0000-0000-000000000000",
            json={"name": "Ghost"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_delete_nonexistent_section(self, client, admin_token):
        resp = await client.delete(
            "/api/v1/floor/sections/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_staff_cannot_create_section(self, client, staff_token):
        resp = await client.post(
            "/api/v1/floor/sections",
            json={"name": "Unauthorized Section"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_list(self, client):
        resp = await client.get("/api/v1/floor/sections")
        assert resp.status_code == 403

    async def test_cannot_delete_section_with_tables(self, client, admin_token):
        create = await client.post(
            "/api/v1/floor/sections",
            json={"name": "Section With Tables"},
            headers=auth(admin_token)
        )
        sid = create.json()["id"]
        await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-SEC-01", "section_id": sid},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/floor/sections/{sid}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "tables" in resp.json()["detail"].lower()