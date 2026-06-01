import pytest
from tests.conftest import auth


MANAGER_PERMISSIONS = [
    {"feature_code": "orders.view", "access_level": "view"},
    {"feature_code": "orders.create", "access_level": "edit"},
    {"feature_code": "billing.view", "access_level": "view"},
    {"feature_code": "billing.void", "access_level": "none"},
    {"feature_code": "hr.view_staff", "access_level": "view"},
]


class TestCreateRolePositive:

    async def test_create_role_with_permissions(self, client, admin_token):
        """TC-ROL-004: Create role with view permissions"""
        resp = await client.post(
            "/api/v1/roles",
            json={"name": "Supervisor", "permissions": MANAGER_PERMISSIONS},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Supervisor"
        assert len(data["permissions"]) == 5

    async def test_create_role_mixed_permissions(self, client, admin_token):
        """TC-ROL-005: Create role with none/view/edit mix"""
        resp = await client.post(
            "/api/v1/roles",
            json={
                "name": "Cashier",
                "permissions": [
                    {"feature_code": "billing.generate", "access_level": "edit"},
                    {"feature_code": "billing.void", "access_level": "none"},
                    {"feature_code": "billing.view", "access_level": "view"},
                ]
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        perms = {p["feature_code"]: p["access_level"] for p in resp.json()["permissions"]}
        assert perms["billing.generate"] == "edit"
        assert perms["billing.void"] == "none"
        assert perms["billing.view"] == "view"

    async def test_create_role_no_permissions(self, client, admin_token):
        """TC-ROL-006: Create role with empty permissions"""
        resp = await client.post(
            "/api/v1/roles",
            json={"name": "Observer", "permissions": []},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["permissions"] == []


class TestCreateRoleNegative:

    async def test_duplicate_role_name(self, client, admin_token):
        """TC-ROL-007: Duplicate role name returns 400"""
        resp = await client.post(
            "/api/v1/roles",
            json={"name": "Supervisor", "permissions": []},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    async def test_non_admin_cannot_create_role(self, client, staff_token):
        """TC-ROL-008: Staff without permission cannot create roles"""
        resp = await client.post(
            "/api/v1/roles",
            json={"name": "Hacker Role", "permissions": []},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_invalid_access_level(self, client, admin_token):
        """TC-ROL-009: Invalid access_level value rejected"""
        resp = await client.post(
            "/api/v1/roles",
            json={
                "name": "BadRole",
                "permissions": [
                    {"feature_code": "orders.view", "access_level": "superuser"}
                ]
            },
            headers=auth(admin_token)
        )
        assert resp.status_code in [400, 422]


class TestListRolesPositive:

    async def test_list_roles(self, client, admin_token):
        """TC-ROL-010: List all roles returns array"""
        resp = await client.get("/api/v1/roles", headers=auth(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    async def test_list_roles_has_correct_fields(self, client, admin_token):
        """Each role in list has required fields"""
        resp = await client.get("/api/v1/roles", headers=auth(admin_token))
        role = resp.json()[0]
        assert "id" in role
        assert "name" in role
        assert "is_system" in role
        assert "permission_count" in role


class TestGetSingleRolePositive:

    async def test_get_role_with_permissions(self, client, admin_token, manager_role):
        """TC-ROL-011: Get role returns full permission list"""
        resp = await client.get(
            f"/api/v1/roles/{manager_role['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == manager_role["id"]
        assert len(data["permissions"]) >= 1
        perm = data["permissions"][0]
        assert "feature_code" in perm
        assert "feature_name" in perm
        assert "module" in perm
        assert "access_level" in perm


class TestGetSingleRoleNegative:

    async def test_non_existent_role(self, client, admin_token):
        """TC-ROL-012: Non-existent role returns 404"""
        resp = await client.get(
            "/api/v1/roles/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404


class TestUpdateRolePositive:

    async def test_update_role_name(self, client, admin_token, manager_role):
        """TC-ROL-013: Update role name"""
        resp = await client.patch(
            f"/api/v1/roles/{manager_role['id']}",
            json={"name": "Senior Manager"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Senior Manager"

    async def test_replace_permissions(self, client, admin_token, manager_role):
        """TC-ROL-014: Replace all permissions"""
        new_perms = [
            {"feature_code": "menu.view", "access_level": "view"},
            {"feature_code": "menu.edit", "access_level": "edit"},
            {"feature_code": "inventory.view", "access_level": "view"},
        ]
        resp = await client.patch(
            f"/api/v1/roles/{manager_role['id']}",
            json={"permissions": new_perms},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()["permissions"]) == 3


class TestDeleteRolePositive:

    async def test_delete_role_with_no_users(self, client, admin_token):
        """TC-ROL-015: Delete role with no assigned users"""
        create = await client.post(
            "/api/v1/roles",
            json={"name": "ToDelete", "permissions": []},
            headers=auth(admin_token)
        )
        role_id = create.json()["id"]
        resp = await client.delete(
            f"/api/v1/roles/{role_id}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200


class TestDeleteRoleNegative:

    async def test_delete_role_with_assigned_users(self, client, admin_token, manager_role, staff_user):
        """TC-ROL-016: Cannot delete role with assigned users"""
        # Assign role to staff
        await client.post(
            "/api/v1/users/assign-role",
            json={"user_id": staff_user["user_id"], "role_template_id": manager_role["id"]},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/roles/{manager_role['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        assert "assigned" in resp.json()["detail"].lower()