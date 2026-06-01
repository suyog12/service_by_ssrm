import pytest
from tests.conftest import auth


class TestAssignRolePositive:

    async def test_assign_role_to_user(self, client, admin_token, staff_user, manager_role):
        """TC-USR-015: Assign role to staff"""
        resp = await client.post(
            "/api/v1/users/assign-role",
            json={"user_id": staff_user["user_id"], "role_template_id": manager_role["id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_role_visible_in_profile(self, client, admin_token, staff_user):
        """After assignment, role shows in profile"""
        resp = await client.get(
            f"/api/v1/users/{staff_user['user_id']}",
            headers=auth(admin_token)
        )
        assert resp.json()["role_template_name"] is not None


class TestAssignRoleNegative:

    async def test_assign_nonexistent_role(self, client, admin_token, staff_user):
        """TC-USR-016: Non-existent role returns 400"""
        resp = await client.post(
            "/api/v1/users/assign-role",
            json={
                "user_id": staff_user["user_id"],
                "role_template_id": "00000000-0000-0000-0000-000000000000"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 400