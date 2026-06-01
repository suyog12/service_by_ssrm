import pytest
from tests.conftest import auth


class TestUpdateUserPositive:

    async def test_update_designation_and_department(self, client, admin_token, staff_user):
        """TC-USR-013: Update designation and department"""
        resp = await client.patch(
            f"/api/v1/users/{staff_user['user_id']}",
            json={"designation": "Head Chef", "department": "Kitchen"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        profile = await client.get(
            f"/api/v1/users/{staff_user['user_id']}",
            headers=auth(admin_token)
        )
        assert profile.json()["designation"] == "Head Chef"
        assert profile.json()["department"] == "Kitchen"

    async def test_partial_update_only_phone(self, client, admin_token, staff_user):
        """TC-USR-014: Partial update only changes specified field"""
        original = await client.get(
            f"/api/v1/users/{staff_user['user_id']}",
            headers=auth(admin_token)
        )
        original_name = original.json()["full_name"]

        await client.patch(
            f"/api/v1/users/{staff_user['user_id']}",
            json={"phone": "9800009999"},
            headers=auth(admin_token)
        )
        updated = await client.get(
            f"/api/v1/users/{staff_user['user_id']}",
            headers=auth(admin_token)
        )
        assert updated.json()["full_name"] == original_name