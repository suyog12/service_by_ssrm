import pytest
from tests.conftest import auth


class TestGuestPositive:

    async def test_create_guest(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hotel/guests",
            json={
                "full_name": "Suyog Mainali",
                "phone": "9800000001",
                "email": "suyog@example.com",
                "nationality": "Nepali",
                "id_type": "citizenship",
                "id_number": "12-34-567"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["full_name"] == "Suyog Mainali"
        assert data["nationality"] == "Nepali"

    async def test_guest_appears_in_list(self, client, admin_token, guest):
        resp = await client.get(
            "/api/v1/hotel/guests",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        ids = [g["id"] for g in resp.json()]
        assert str(guest["id"]) in ids

    async def test_get_single_guest(self, client, admin_token, guest):
        resp = await client.get(
            f"/api/v1/hotel/guests/{guest['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == guest["full_name"]

    async def test_update_guest(self, client, admin_token, guest):
        resp = await client.patch(
            f"/api/v1/hotel/guests/{guest['id']}",
            json={"nationality": "American", "company_name": "Acme Corp"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["nationality"] == "American"

    async def test_search_guest_by_name(self, client, admin_token, guest):
        resp = await client.get(
            f"/api/v1/hotel/guests?search={guest['full_name'][:5]}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_search_guest_by_phone(self, client, admin_token, guest):
        resp = await client.get(
            f"/api/v1/hotel/guests?search={guest['phone']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_corporate_guest(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hotel/guests",
            json={
                "full_name": "Corporate Guest",
                "company_name": "Everest Trekking Pvt Ltd",
                "company_pan": "123456789",
                "is_corporate": True
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["is_corporate"] is True

    async def test_staff_can_create_guest(self, client, staff_token):
        resp = await client.post(
            "/api/v1/hotel/guests",
            json={"full_name": "Staff Created Guest"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 201
        
    async def test_guest_with_phone_links_to_customer(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hotel/guests",
            json={"full_name": "Linked Guest", "phone": "9822000001"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["customer_id"] is not None

    async def test_same_phone_reuses_existing_customer(self, client, admin_token):
        first = await client.post(
            "/api/v1/hotel/guests",
            json={"full_name": "Repeat Guest", "phone": "9822000002"},
            headers=auth(admin_token)
        )
        assert first.status_code == 201
        first_customer_id = first.json()["customer_id"]
        assert first_customer_id is not None

        second = await client.post(
            "/api/v1/hotel/guests",
            json={"full_name": "Repeat Guest Again", "phone": "9822000002"},
            headers=auth(admin_token)
        )
        assert second.status_code == 201
        assert second.json()["customer_id"] == first_customer_id

    async def test_guest_without_phone_has_no_customer_id(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hotel/guests",
            json={"full_name": "No Phone Guest"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["customer_id"] is None


class TestGuestNegative:

    async def test_empty_name_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hotel/guests",
            json={"full_name": ""},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_get_nonexistent_guest(self, client, admin_token):
        resp = await client.get(
            "/api/v1/hotel/guests/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_unauthenticated_cannot_list(self, client):
        resp = await client.get("/api/v1/hotel/guests")
        assert resp.status_code == 403


@pytest.fixture
async def guest(client, admin_token):
    resp = await client.post(
        "/api/v1/hotel/guests",
        json={
            "full_name": "Test Guest Nepal",
            "phone": "9811111111",
            "email": "guest@test.com",
            "nationality": "Nepali"
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()