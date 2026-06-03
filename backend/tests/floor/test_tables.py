import pytest
from tests.conftest import auth


@pytest.fixture
async def section(client, admin_token):
    resp = await client.post(
        "/api/v1/floor/sections",
        json={"name": "Test Section"},
        headers=auth(admin_token)
    )
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        sections = await client.get("/api/v1/floor/sections", headers=auth(admin_token))
        for s in sections.json():
            if s["name"] == "Test Section":
                return s
    assert resp.status_code == 201
    return resp.json()


class TestTablePositive:

    async def test_admin_creates_table(self, client, admin_token):
        resp = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-01", "capacity": 4},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["table_number"] == "T-01"
        assert data["capacity"] == 4
        assert data["status"] == "available"
        assert "id" in data

    async def test_create_table_with_section(self, client, admin_token, section):
        resp = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-02", "capacity": 2, "section_id": section["id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["section_id"] == section["id"]
        assert resp.json()["section_name"] == section["name"]

    async def test_table_appears_in_list(self, client, admin_token):
        await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-LIST-01"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/floor/tables",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        numbers = [t["table_number"] for t in resp.json()]
        assert "T-LIST-01" in numbers

    async def test_get_single_table(self, client, admin_token):
        create = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-GET-01"},
            headers=auth(admin_token)
        )
        tid = create.json()["id"]
        resp = await client.get(
            f"/api/v1/floor/tables/{tid}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == tid

    async def test_list_tables_filtered_by_section(self, client, admin_token, section):
        await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-SEC-FILTER-01", "section_id": section["id"]},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/floor/tables?section_id={section['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        for table in resp.json():
            assert table["section_id"] == section["id"]

    async def test_update_table_status(self, client, admin_token):
        create = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-STATUS-01"},
            headers=auth(admin_token)
        )
        tid = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/floor/tables/{tid}",
            json={"status": "occupied"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "occupied"

    async def test_update_table_capacity(self, client, admin_token):
        create = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-CAP-01", "capacity": 2},
            headers=auth(admin_token)
        )
        tid = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/floor/tables/{tid}",
            json={"capacity": 6},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["capacity"] == 6

    async def test_assign_table_to_section(self, client, admin_token, section):
        create = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-ASSIGN-01"},
            headers=auth(admin_token)
        )
        tid = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/floor/tables/{tid}",
            json={"section_id": section["id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["section_id"] == section["id"]

    async def test_all_status_values_accepted(self, client, admin_token):
        for status in ["available", "occupied", "reserved", "needs_cleaning"]:
            create = await client.post(
                "/api/v1/floor/tables",
                json={"table_number": f"T-STAT-{status[:3].upper()}"},
                headers=auth(admin_token)
            )
            tid = create.json()["id"]
            resp = await client.patch(
                f"/api/v1/floor/tables/{tid}",
                json={"status": status},
                headers=auth(admin_token)
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == status

    async def test_delete_available_table(self, client, admin_token):
        create = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-DEL-01"},
            headers=auth(admin_token)
        )
        tid = create.json()["id"]
        resp = await client.delete(
            f"/api/v1/floor/tables/{tid}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_staff_can_list_tables(self, client, staff_token):
        resp = await client.get(
            "/api/v1/floor/tables",
            headers=auth(staff_token)
        )
        assert resp.status_code == 200

    async def test_staff_can_get_single_table(self, client, admin_token, staff_token):
        create = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-STAFF-READ-01"},
            headers=auth(admin_token)
        )
        tid = create.json()["id"]
        resp = await client.get(
            f"/api/v1/floor/tables/{tid}",
            headers=auth(staff_token)
        )
        assert resp.status_code == 200


class TestTableNegative:

    async def test_duplicate_table_number_rejected(self, client, admin_token):
        await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-DUP-01"},
            headers=auth(admin_token)
        )
        resp = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-DUP-01"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    async def test_invalid_status_rejected(self, client, admin_token):
        create = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-BADSTAT-01"},
            headers=auth(admin_token)
        )
        tid = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/floor/tables/{tid}",
            json={"status": "on_fire"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_zero_capacity_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-ZEROCAP-01", "capacity": 0},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_nonexistent_section_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/floor/tables",
            json={
                "table_number": "T-NOSEC-01",
                "section_id": "00000000-0000-0000-0000-000000000000"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_get_nonexistent_table(self, client, admin_token):
        resp = await client.get(
            "/api/v1/floor/tables/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_delete_nonexistent_table(self, client, admin_token):
        resp = await client.delete(
            "/api/v1/floor/tables/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_cannot_delete_occupied_table(self, client, admin_token):
        create = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-OCC-DEL-01"},
            headers=auth(admin_token)
        )
        tid = create.json()["id"]
        await client.patch(
            f"/api/v1/floor/tables/{tid}",
            json={"status": "occupied"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/floor/tables/{tid}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_staff_cannot_create_table(self, client, staff_token):
        resp = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "T-UNAUTH-01"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_list(self, client):
        resp = await client.get("/api/v1/floor/tables")
        assert resp.status_code == 403