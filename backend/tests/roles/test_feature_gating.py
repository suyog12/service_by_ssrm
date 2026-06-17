import pytest
from tests.conftest import auth


class TestAdminBypassesFeatureGating:

    async def test_admin_can_access_all_menu_endpoints(self, client, admin_token):
        resp = await client.get("/api/v1/menu/categories", headers=auth(admin_token))
        assert resp.status_code == 200

    async def test_admin_can_access_all_billing_endpoints(self, client, admin_token):
        resp = await client.get("/api/v1/billing/bills", headers=auth(admin_token))
        assert resp.status_code == 200

    async def test_admin_can_access_all_inventory_endpoints(self, client, admin_token):
        resp = await client.get("/api/v1/inventory/suppliers", headers=auth(admin_token))
        assert resp.status_code == 200

    async def test_admin_can_access_all_hotel_endpoints(self, client, admin_token):
        resp = await client.get("/api/v1/hotel/room-types", headers=auth(admin_token))
        assert resp.status_code == 200

    async def test_admin_can_access_all_floor_endpoints(self, client, admin_token):
        resp = await client.get("/api/v1/floor/sections", headers=auth(admin_token))
        assert resp.status_code == 200

    async def test_admin_can_access_all_order_endpoints(self, client, admin_token):
        resp = await client.get("/api/v1/orders", headers=auth(admin_token))
        assert resp.status_code == 200

    async def test_admin_can_access_outlets(self, client, admin_token):
        resp = await client.get("/api/v1/outlets", headers=auth(admin_token))
        assert resp.status_code == 200

    async def test_admin_can_access_hr_endpoints(self, client, admin_token):
        resp = await client.get("/api/v1/users", headers=auth(admin_token))
        assert resp.status_code == 200


class TestStaffWithPermissionCanAccess:

    async def test_staff_with_menu_view_can_list_categories(
        self, client, staff_token
    ):
        resp = await client.get("/api/v1/menu/categories", headers=auth(staff_token))
        assert resp.status_code == 200

    async def test_staff_with_menu_view_can_list_items(
        self, client, staff_token
    ):
        resp = await client.get("/api/v1/menu/items", headers=auth(staff_token))
        assert resp.status_code == 200

    async def test_staff_with_orders_create_can_create_order(
        self, client, admin_token, staff_token
    ):
        resp = await client.post(
            "/api/v1/orders",
            json={"order_type": "takeaway"},
            headers=auth(staff_token)
        )
        # 201 or 422 (validation) — either means the endpoint was reached
        assert resp.status_code in (201, 422)

    async def test_staff_with_billing_view_can_list_bills(
        self, client, staff_token
    ):
        resp = await client.get("/api/v1/billing/bills", headers=auth(staff_token))
        assert resp.status_code == 200

    async def test_staff_with_inventory_view_can_list_suppliers(
        self, client, staff_token
    ):
        resp = await client.get("/api/v1/inventory/suppliers", headers=auth(staff_token))
        assert resp.status_code == 200

    async def test_staff_with_hotel_rooms_view_can_list_rooms(
        self, client, staff_token
    ):
        resp = await client.get("/api/v1/hotel/room-types", headers=auth(staff_token))
        assert resp.status_code == 200

    async def test_staff_with_hotel_guests_edit_can_create_guest(
        self, client, staff_token
    ):
        resp = await client.post(
            "/api/v1/hotel/guests",
            json={"full_name": "Feature Gate Test Guest"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 201

    async def test_staff_with_hotel_checkin_can_access_reservations(
        self, client, staff_token
    ):
        resp = await client.get("/api/v1/hotel/reservations", headers=auth(staff_token))
        assert resp.status_code == 200

    async def test_staff_with_floor_view_can_list_tables(
        self, client, staff_token
    ):
        resp = await client.get("/api/v1/floor/tables", headers=auth(staff_token))
        assert resp.status_code == 200

    async def test_staff_with_outlets_view_can_list_outlets(
        self, client, staff_token
    ):
        resp = await client.get("/api/v1/outlets", headers=auth(staff_token))
        assert resp.status_code == 200


class TestStaffWithoutPermissionGets403:

    async def test_staff_cannot_create_menu_category(self, client, staff_token):
        resp = await client.post(
            "/api/v1/menu/categories",
            json={"name": "Unauthorized Category"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_create_menu_item(self, client, staff_token):
        resp = await client.post(
            "/api/v1/menu/items",
            json={"name": "Unauthorized Item", "price": 100},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_create_ingredient(self, client, staff_token):
        resp = await client.post(
            "/api/v1/ingredients",
            json={"name": "Unauthorized Ingredient", "unit": "g"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_create_supplier(self, client, staff_token):
        resp = await client.post(
            "/api/v1/inventory/suppliers",
            json={"name": "Unauthorized Supplier"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_add_stock(self, client, staff_token):
        resp = await client.post(
            "/api/v1/inventory/stock/add",
            json={"ingredient_id": "00000000-0000-0000-0000-000000000000", "quantity": 10},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_create_purchase_order(self, client, staff_token):
        resp = await client.post(
            "/api/v1/inventory/purchase-orders",
            json={"supplier_id": "00000000-0000-0000-0000-000000000000"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_create_outlet(self, client, staff_token):
        resp = await client.post(
            "/api/v1/outlets",
            json={"name": "Unauthorized Outlet", "type": "restaurant"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_create_room_type(self, client, staff_token):
        resp = await client.post(
            "/api/v1/hotel/room-types",
            json={"name": "Unauthorized Room Type", "base_price": "3000"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_update_billing_settings(self, client, staff_token):
        resp = await client.patch(
            "/api/v1/billing/settings",
            json={"vat_mode": "inclusive"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_create_credit_account(self, client, staff_token):
        resp = await client.post(
            "/api/v1/billing/credit-accounts",
            json={"account_type": "corporate", "display_name": "Test Corp", "credit_limit": 10000},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_void_bill(self, client, staff_token):
        resp = await client.post(
            "/api/v1/billing/bills/00000000-0000-0000-0000-000000000000/void?reason=test",
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_create_role(self, client, staff_token):
        resp = await client.post(
            "/api/v1/roles",
            json={"name": "Unauthorized Role", "permissions": []},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_create_staff_user(self, client, staff_token):
        resp = await client.post(
            "/api/v1/users",
            json={"full_name": "Unauthorized User", "email": "unauth@test.com"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_create_floor_section(self, client, staff_token):
        resp = await client.post(
            "/api/v1/floor/sections",
            json={"name": "Unauthorized Section"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_staff_cannot_create_table(self, client, staff_token):
        resp = await client.post(
            "/api/v1/floor/tables",
            json={"table_number": "99", "capacity": 4},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403


class TestStaffWithNoRoleGets403:

    async def test_roleless_staff_cannot_list_menu(
        self, client, roleless_staff_token
    ):
        resp = await client.get("/api/v1/menu/categories", headers=auth(roleless_staff_token))
        assert resp.status_code == 403

    async def test_roleless_staff_cannot_list_orders(
        self, client, roleless_staff_token
    ):
        resp = await client.get("/api/v1/orders", headers=auth(roleless_staff_token))
        assert resp.status_code == 403

    async def test_roleless_staff_cannot_list_bills(
        self, client, roleless_staff_token
    ):
        resp = await client.get("/api/v1/billing/bills", headers=auth(roleless_staff_token))
        assert resp.status_code == 403

    async def test_roleless_staff_cannot_list_hotel_rooms(
        self, client, roleless_staff_token
    ):
        resp = await client.get("/api/v1/hotel/room-types", headers=auth(roleless_staff_token))
        assert resp.status_code == 403

    async def test_roleless_staff_cannot_list_inventory(
        self, client, roleless_staff_token
    ):
        resp = await client.get("/api/v1/inventory/suppliers", headers=auth(roleless_staff_token))
        assert resp.status_code == 403

    async def test_roleless_staff_can_still_access_own_profile(
        self, client, roleless_staff_token
    ):
        # /auth/me uses get_current_user not require_feature — always accessible
        resp = await client.get("/api/v1/auth/me", headers=auth(roleless_staff_token))
        assert resp.status_code == 200

    async def test_roleless_staff_can_list_features(
        self, client, roleless_staff_token
    ):
        # /roles/features uses get_current_user — always accessible
        resp = await client.get("/api/v1/roles/features", headers=auth(roleless_staff_token))
        assert resp.status_code == 200


class TestUserOverrideTakesPrecedence:

    async def test_override_grants_access_role_denies(
        self, client, admin_token, db, registered_tenant
    ):
        # Create a user with no role
        create = await client.post(
            "/api/v1/users",
            json={"full_name": "Override Test User", "email": "override@test.com"},
            headers=auth(admin_token)
        )
        assert create.status_code == 201
        user_id = create.json()["user_id"]

        from app.utils.password import hash_password
        await db.execute(
            "UPDATE core.users SET password_hash=$1, must_change_password=FALSE WHERE id=$2",
            hash_password("Override@123"), user_id
        )

        # Login — no role, should get 403 on protected routes
        login = await client.post("/api/v1/auth/login", json={
            "email": "override@test.com",
            "password": "Override@123",
            "tenant_slug": "test-hotel-nepal"
        })
        token = login.json()["access_token"]

        resp = await client.get("/api/v1/menu/categories", headers=auth(token))
        assert resp.status_code == 403

        # Grant override for menu.view
        override = await client.post(
            "/api/v1/users/permissions",
            json={
                "user_id": user_id,
                "feature_code": "menu.view",
                "access_level": "view"
            },
            headers=auth(admin_token)
        )
        assert override.status_code == 200

        # Re-login to get fresh token
        login2 = await client.post("/api/v1/auth/login", json={
            "email": "override@test.com",
            "password": "Override@123",
            "tenant_slug": "test-hotel-nepal"
        })
        token2 = login2.json()["access_token"]

        # Now should be able to access
        resp2 = await client.get("/api/v1/menu/categories", headers=auth(token2))
        assert resp2.status_code == 200

    async def test_override_denies_access_role_grants(
        self, client, admin_token, db, staff_token, staff_user, registered_tenant
    ):
        # staff_token has billing.view via staff_role
        resp = await client.get("/api/v1/billing/bills", headers=auth(staff_token))
        assert resp.status_code == 200

        # Set override to deny billing.view
        override = await client.post(
            "/api/v1/users/permissions",
            json={
                "user_id": staff_user["user_id"],
                "feature_code": "billing.view",
                "access_level": "none"
            },
            headers=auth(admin_token)
        )
        assert override.status_code == 200

        # Re-login to get fresh token
        login = await client.post("/api/v1/auth/login", json={
            "email": staff_user["email"],
            "password": staff_user["password"],
            "tenant_slug": "test-hotel-nepal"
        })
        new_token = login.json()["access_token"]

        # Now should be denied
        resp2 = await client.get("/api/v1/billing/bills", headers=auth(new_token))
        assert resp2.status_code == 403

    async def test_edit_override_allows_write_when_role_has_view_only(
        self, client, admin_token, db, registered_tenant
    ):
        # Create user with view-only billing role
        create = await client.post(
            "/api/v1/users",
            json={"full_name": "Edit Override User", "email": "editoverride@test.com"},
            headers=auth(admin_token)
        )
        assert create.status_code == 201
        user_id = create.json()["user_id"]

        # Create view-only role
        role = await client.post(
            "/api/v1/roles",
            json={
                "name": "ViewOnlyBilling",
                "permissions": [
                    {"feature_code": "billing.void", "access_level": "view"}
                ]
            },
            headers=auth(admin_token)
        )
        assert role.status_code == 201

        await client.post(
            "/api/v1/users/assign-role",
            json={"user_id": user_id, "role_template_id": role.json()["id"]},
            headers=auth(admin_token)
        )

        from app.utils.password import hash_password
        await db.execute(
            "UPDATE core.users SET password_hash=$1, must_change_password=FALSE WHERE id=$2",
            hash_password("EditOverride@123"), user_id
        )

        login = await client.post("/api/v1/auth/login", json={
            "email": "editoverride@test.com",
            "password": "EditOverride@123",
            "tenant_slug": "test-hotel-nepal"
        })
        token = login.json()["access_token"]

        # Cannot void (needs edit)
        resp = await client.post(
            "/api/v1/billing/bills/00000000-0000-0000-0000-000000000000/void?reason=test",
            headers=auth(token)
        )
        assert resp.status_code == 403

        # Grant edit override
        await client.post(
            "/api/v1/users/permissions",
            json={
                "user_id": user_id,
                "feature_code": "billing.void",
                "access_level": "edit"
            },
            headers=auth(admin_token)
        )

        login2 = await client.post("/api/v1/auth/login", json={
            "email": "editoverride@test.com",
            "password": "EditOverride@123",
            "tenant_slug": "test-hotel-nepal"
        })
        token2 = login2.json()["access_token"]

        # Now passes feature gate (404 means endpoint reached, bill not found)
        resp2 = await client.post(
            "/api/v1/billing/bills/00000000-0000-0000-0000-000000000000/void?reason=test",
            headers=auth(token2)
        )
        assert resp2.status_code == 404


class TestMustChangePasswordBlocksFeatureGatedRoutes:

    async def test_must_change_password_blocks_menu_access(
        self, client, admin_token, db, registered_tenant
    ):
        create = await client.post(
            "/api/v1/users",
            json={"full_name": "Must Change User", "email": "mustchange@test.com"},
            headers=auth(admin_token)
        )
        assert create.status_code == 201
        user_id = create.json()["user_id"]

        from app.utils.password import hash_password
        await db.execute(
            "UPDATE core.users SET password_hash=$1, must_change_password=TRUE WHERE id=$2",
            hash_password("MustChange@123"), user_id
        )

        login = await client.post("/api/v1/auth/login", json={
            "email": "mustchange@test.com",
            "password": "MustChange@123",
            "tenant_slug": "test-hotel-nepal"
        })
        token = login.json()["access_token"]

        resp = await client.get("/api/v1/menu/categories", headers=auth(token))
        assert resp.status_code == 403
        assert "change your password" in resp.json()["detail"].lower()

    async def test_must_change_password_blocks_orders_access(
        self, client, admin_token, db, registered_tenant
    ):
        create = await client.post(
            "/api/v1/users",
            json={"full_name": "Must Change User 2", "email": "mustchange2@test.com"},
            headers=auth(admin_token)
        )
        assert create.status_code == 201
        user_id = create.json()["user_id"]

        from app.utils.password import hash_password
        await db.execute(
            "UPDATE core.users SET password_hash=$1, must_change_password=TRUE WHERE id=$2",
            hash_password("MustChange@123"), user_id
        )

        login = await client.post("/api/v1/auth/login", json={
            "email": "mustchange2@test.com",
            "password": "MustChange@123",
            "tenant_slug": "test-hotel-nepal"
        })
        token = login.json()["access_token"]

        resp = await client.get("/api/v1/orders", headers=auth(token))
        assert resp.status_code == 403


class TestUnauthenticatedGets403:

    async def test_no_token_menu(self, client):
        resp = await client.get("/api/v1/menu/categories")
        assert resp.status_code == 403

    async def test_no_token_orders(self, client):
        resp = await client.get("/api/v1/orders")
        assert resp.status_code == 403

    async def test_no_token_billing(self, client):
        resp = await client.get("/api/v1/billing/bills")
        assert resp.status_code == 403

    async def test_no_token_inventory(self, client):
        resp = await client.get("/api/v1/inventory/suppliers")
        assert resp.status_code == 403

    async def test_no_token_hotel_rooms(self, client):
        resp = await client.get("/api/v1/hotel/room-types")
        assert resp.status_code == 403

    async def test_no_token_hotel_reservations(self, client):
        resp = await client.get("/api/v1/hotel/reservations")
        assert resp.status_code == 403

    async def test_no_token_hotel_guests(self, client):
        resp = await client.get("/api/v1/hotel/guests")
        assert resp.status_code == 403

    async def test_no_token_floor(self, client):
        resp = await client.get("/api/v1/floor/sections")
        assert resp.status_code == 403

    async def test_no_token_outlets(self, client):
        resp = await client.get("/api/v1/outlets")
        assert resp.status_code == 403

    async def test_no_token_users(self, client):
        resp = await client.get("/api/v1/users")
        assert resp.status_code == 403

    async def test_no_token_roles(self, client):
        resp = await client.get("/api/v1/roles")
        assert resp.status_code == 403


@pytest.fixture
async def roleless_staff_token(client, admin_token, db, registered_tenant):
    """Staff user with no role assigned."""
    create = await client.post(
        "/api/v1/users",
        json={"full_name": "Roleless Staff", "email": "roleless@testhotel.com"},
        headers=auth(admin_token)
    )
    if create.status_code == 400 and "already exists" in create.json().get("detail", ""):
        row = await db.fetchrow(
            "SELECT id FROM core.users WHERE email = $1", "roleless@testhotel.com"
        )
        user_id = str(row["id"])
    else:
        assert create.status_code == 201, create.text
        user_id = create.json()["user_id"]

    from app.utils.password import hash_password
    await db.execute(
        "UPDATE core.users SET password_hash=$1, must_change_password=FALSE WHERE id=$2",
        hash_password("Roleless@123"), user_id
    )

    login = await client.post("/api/v1/auth/login", json={
        "email": "roleless@testhotel.com",
        "password": "Roleless@123",
        "tenant_slug": "test-hotel-nepal"
    })
    assert login.status_code == 200, login.text
    return login.json()["access_token"]