import pytest
from tests.conftest import auth


class TestListUsersPositive:

    async def test_admin_lists_all_staff(self, client, admin_token):
        """TC-USR-008: Admin gets list of all staff"""
        resp = await client.get("/api/v1/users", headers=auth(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    async def test_list_has_correct_fields(self, client, admin_token):
        """Each user in list has expected fields"""
        resp = await client.get("/api/v1/users", headers=auth(admin_token))
        user = resp.json()[0]
        assert "user_id" in user
        assert "full_name" in user
        assert "email" in user
        assert "is_admin" in user


class TestListUsersSecurity:

    async def test_tenant_isolation_in_list(self, client, admin_token, admin_token_b):
        """TC-USR-009: Tenant A cannot see Tenant B users"""
        resp_a = await client.get("/api/v1/users", headers=auth(admin_token))
        resp_b = await client.get("/api/v1/users", headers=auth(admin_token_b))

        emails_a = {u["email"] for u in resp_a.json()}
        emails_b = {u["email"] for u in resp_b.json()}

        assert len(emails_a.intersection(emails_b)) == 0