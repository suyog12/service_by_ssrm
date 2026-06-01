import pytest
from tests.conftest import auth


class TestCreateUserPositive:

    async def test_create_staff_returns_201(self, client, admin_token):
        """TC-USR-001: Admin creates staff account"""
        resp = await client.post(
            "/api/v1/users",
            json={
                "full_name": "New Staff Member",
                "email": "newstaff@testhotel.com",
                "phone": "9800001111",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "user_id" in data
        assert data["email"] == "newstaff@testhotel.com"
        assert "created successfully" in data["message"].lower()

    async def test_created_user_has_must_change_password(self, client, admin_token, db):
        """Created staff must change password on first login"""
        resp = await client.post(
            "/api/v1/users",
            json={"full_name": "Another Staff", "email": "anotherstaff@testhotel.com"},
            headers=auth(admin_token)
        )
        user_id = resp.json()["user_id"]
        row = await db.fetchrow(
            "SELECT must_change_password FROM core.users WHERE id = $1", user_id
        )
        assert row["must_change_password"] is True

    async def test_staff_with_role(self, client, admin_token, manager_role):
        """Create staff with role assigned at creation"""
        resp = await client.post(
            "/api/v1/users",
            json={
                "full_name": "Roled Staff",
                "email": "roledstaff@testhotel.com",
                "role_template_id": manager_role["id"]
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201


class TestCreateUserNegative:

    async def test_duplicate_email(self, client, admin_token):
        """TC-USR-005: Duplicate email in same tenant returns 400"""
        resp = await client.post(
            "/api/v1/users",
            json={"full_name": "Duplicate", "email": "newstaff@testhotel.com"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    async def test_missing_full_name(self, client, admin_token):
        """TC-USR-007: Missing full_name returns 422"""
        resp = await client.post(
            "/api/v1/users",
            json={"email": "nofullname@testhotel.com"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_unauthorized_staff_cannot_create(self, client, staff_token):
        """TC-USR-006: Staff without hr.create_staff cannot create users"""
        resp = await client.post(
            "/api/v1/users",
            json={"full_name": "Unauthorized", "email": "unauth@testhotel.com"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403