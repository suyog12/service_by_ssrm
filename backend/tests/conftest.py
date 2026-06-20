import pytest
import asyncpg
from httpx import AsyncClient, ASGITransport
from app.core.config import settings
from app.core import database as db_module


TENANT_SCHEMA = "tenant_test_hotel_nepal"
TENANT_SCHEMA_B = "tenant_second_restaurant_nepal"


# Reset pool on every test 

@pytest.fixture(autouse=True)
async def reset_pool():
    await db_module.close_pool()
    yield
    await db_module.close_pool()


# Clean tables after every test 

@pytest.fixture(autouse=True)
async def clean_inventory():
    yield
    conn = await asyncpg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        statement_cache_size=0,
    )
    try:
        for schema in [TENANT_SCHEMA, TENANT_SCHEMA_B]:
            # Bills and payments
            for table in [
                "payments",
                "bill_discounts",
                "discount_approvals",
                "credit_transactions",
                "credit_accounts",
                "bills",
            ]:
                try:
                    await conn.execute(f'DELETE FROM "{schema}".{table}')
                except Exception:
                    pass

            # Orders, KOTs
            for table in [
                "stock_deductions",
                "kots",
                "order_items",
                "order_status_log",
                "orders",
            ]:
                try:
                    await conn.execute(f'DELETE FROM "{schema}".{table}')
                except Exception:
                    pass

            # Menu items and categories (test-created ones)
            try:
                await conn.execute(
                    f'DELETE FROM "{schema}".item_ingredients'
                )
                await conn.execute(
                    f'DELETE FROM "{schema}".menu_items'
                )
                await conn.execute(
                    f'DELETE FROM "{schema}".menu_categories'
                )
            except Exception:
                pass

            # Table reservations and merges (must clear before tables/sections,
            # since they FK-reference tables)
            for table in ["table_merges", "table_reservations"]:
                try:
                    await conn.execute(f'DELETE FROM "{schema}".{table}')
                except Exception:
                    pass

            # Tables and sections
            for table in ["tables", "sections"]:
                try:
                    await conn.execute(f'DELETE FROM "{schema}".{table}')
                except Exception:
                    pass
            
            # Hotel tables
            for table in [
                "guest_folio",
                "room_charges",
                "housekeeping_tasks",
                "hotel_reservations",
                "rooms",
                "pricing_rules",
                "room_type_minibar",
                "room_type_housekeeping_kit",
                "room_types",
                "guests",
            ]:
                try:
                    await conn.execute(f'DELETE FROM "{schema}".{table}')
                except Exception:
                    pass

            # Customer profile tables
            for table in [
                "customer_visit_notes",
                "customer_preferences",
                "loyalty_transactions",
                "loyalty_accounts",
                "customers",
            ]:
                try:
                    await conn.execute(f'DELETE FROM "{schema}".{table}')
                except Exception:
                    pass
                
            # Inventory
            for table in [
                "po_items",
                "purchase_orders",
                "stock_adjustments",
                "stock_batches",
                "suppliers",
                "ingredients",
            ]:
                try:
                    await conn.execute(f'DELETE FROM "{schema}".{table}')
                except Exception:
                    pass

            # Outlets — delete non-default only, keep billing settings for default
            # Refresh tokens
            try:
                await conn.execute("DELETE FROM core.refresh_tokens")
            except Exception:
                pass
            try:
                await conn.execute(
                    f"""
                    DELETE FROM "{schema}".billing_settings
                    WHERE outlet_id IN (
                        SELECT id FROM "{schema}".outlets
                        WHERE is_default = FALSE
                    )
                    """
                )
                await conn.execute(
                    f"""
                    DELETE FROM "{schema}".outlets
                    WHERE is_default = FALSE
                    """
                )
                await conn.execute(
                    f"""
                    INSERT INTO "{schema}".billing_settings (outlet_id)
                    SELECT id FROM "{schema}".outlets WHERE is_default = TRUE
                    ON CONFLICT (outlet_id) DO NOTHING
                    """
                )
            except Exception:
                pass

    finally:
        await conn.close()

# HTTP client per test 

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=__import__('app.main', fromlist=['app']).app),
        base_url="http://test"
    ) as c:
        yield c


# One-time DB cleanup before session 

@pytest.fixture(autouse=True, scope="session")
def clean_db_once():
    import asyncio
    import asyncpg as apg

    async def _clean():
        conn = await asyncpg.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            statement_cache_size=0,
        )
        try:
            rows = await conn.fetch(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'tenant_%'"
            )
            for row in rows:
                await conn.execute(
                    f'DROP SCHEMA IF EXISTS "{row["schema_name"]}" CASCADE'
                )
            await conn.execute("DELETE FROM core.refresh_tokens")
            await conn.execute("DELETE FROM core.users")
            await conn.execute("DELETE FROM core.tenants")
        finally:
            await conn.close()

    asyncio.get_event_loop_policy().get_event_loop().run_until_complete(_clean())
    yield


# Shared test data 

TEST_BUSINESS = {
    "business_name": "Test Hotel Nepal",
    "business_type": "both",
    "business_email": "admin@testhotel.com",
    "business_phone": "9800000001",
    "city": "Kathmandu",
    "admin_full_name": "Test Admin",
    "admin_email": "testadmin@testhotel.com",
    "admin_password": "TestPass@123",
    "admin_phone": "9800000001"
}

TEST_BUSINESS_B = {
    "business_name": "Second Restaurant Nepal",
    "business_type": "restaurant",
    "business_email": "admin@secondrest.com",
    "business_phone": "9800000002",
    "city": "Pokhara",
    "admin_full_name": "Second Admin",
    "admin_email": "secondadmin@secondrest.com",
    "admin_password": "TestPass@123",
    "admin_phone": "9800000002"
}


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# Fixtures 

@pytest.fixture
async def registered_tenant(client, db):
    resp = await client.post("/api/v1/auth/register", json=TEST_BUSINESS)
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        from app.utils.password import hash_password
        await db.execute(
            """
            UPDATE core.users SET password_hash = $1, must_change_password = FALSE
            WHERE email = $2
            """,
            hash_password(TEST_BUSINESS["admin_password"]),
            TEST_BUSINESS["admin_email"]
        )
        login = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        assert login.status_code == 200, f"Login failed after password reset: {login.text}"
        d = login.json()
        result = {
            "schema_name": d["schema_name"],
            "tenant_id": d["user_id"],
            "admin_user_id": d["user_id"]
        }
    else:
        assert resp.status_code == 201, resp.text
        result = resp.json()

    # Always upgrade to max tier — runs for both new and existing tenants
    await db.execute(
        "UPDATE core.tenants SET subscription_tier = 'max' WHERE slug = $1",
        "test-hotel-nepal"
    )
    return result


@pytest.fixture
async def registered_tenant_b(client, db):
    resp = await client.post("/api/v1/auth/register", json=TEST_BUSINESS_B)
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        from app.utils.password import hash_password
        await db.execute(
            """
            UPDATE core.users SET password_hash = $1, must_change_password = FALSE
            WHERE email = $2
            """,
            hash_password(TEST_BUSINESS_B["admin_password"]),
            TEST_BUSINESS_B["admin_email"]
        )
        login = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS_B["admin_email"],
            "password": TEST_BUSINESS_B["admin_password"],
            "tenant_slug": "second-restaurant-nepal"
        })
        assert login.status_code == 200, f"Login failed after password reset: {login.text}"
        d = login.json()
        return {
            "schema_name": d["schema_name"],
            "tenant_id": d["user_id"],
            "admin_user_id": d["user_id"]
        }
    assert resp.status_code == 201, resp.text
    await db.execute(
        "UPDATE core.tenants SET subscription_tier = 'max' WHERE slug = $1",
        "second-restaurant-nepal"
    )
    return resp.json()


@pytest.fixture
async def admin_token(client, registered_tenant):
    resp = await client.post("/api/v1/auth/login", json={
        "email": TEST_BUSINESS["admin_email"],
        "password": TEST_BUSINESS["admin_password"],
        "tenant_slug": "test-hotel-nepal"
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
async def admin_refresh_token(client, registered_tenant):
    resp = await client.post("/api/v1/auth/login", json={
        "email": TEST_BUSINESS["admin_email"],
        "password": TEST_BUSINESS["admin_password"],
        "tenant_slug": "test-hotel-nepal"
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["refresh_token"]


@pytest.fixture
async def admin_token_b(client, registered_tenant_b):
    resp = await client.post("/api/v1/auth/login", json={
        "email": TEST_BUSINESS_B["admin_email"],
        "password": TEST_BUSINESS_B["admin_password"],
        "tenant_slug": "second-restaurant-nepal"
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
async def staff_token(client, staff_user, registered_tenant):
    resp = await client.post("/api/v1/auth/login", json={
        "email": staff_user["email"],
        "password": staff_user["password"],
        "tenant_slug": "test-hotel-nepal"
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
async def manager_role(client, admin_token):
    resp = await client.post(
        "/api/v1/roles",
        json={
            "name": "Manager",
            "description": "Operations manager",
            "permissions": [
                {"feature_code": "orders.view",   "access_level": "view"},
                {"feature_code": "orders.create", "access_level": "edit"},
                {"feature_code": "billing.view",  "access_level": "view"},
                {"feature_code": "billing.void",  "access_level": "none"},
                {"feature_code": "hr.view_staff", "access_level": "view"},
            ]
        },
        headers=auth(admin_token)
    )
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        roles = await client.get("/api/v1/roles", headers=auth(admin_token))
        for role in roles.json():
            if role["name"] == "Manager":
                return role
    assert resp.status_code == 201, resp.text
    return resp.json()

@pytest.fixture
async def staff_role(client, admin_token):
    """Minimal waiter-level role — can create/view orders and view menu only."""
    resp = await client.post(
        "/api/v1/roles",
        json={
            "name": "Staff",
            "description": "General staff role for testing",
            "permissions": [
                {"feature_code": "orders.view",        "access_level": "view"},
                {"feature_code": "orders.create",      "access_level": "edit"},
                {"feature_code": "orders.edit",        "access_level": "edit"},
                {"feature_code": "orders.cancel",      "access_level": "edit"},
                {"feature_code": "orders.assign_chef", "access_level": "edit"},
                {"feature_code": "menu.view",          "access_level": "view"},
                {"feature_code": "floor.tables",       "access_level": "view"},
                {"feature_code": "outlets.view",       "access_level": "view"},
                {"feature_code": "billing.view",       "access_level": "view"},
                {"feature_code": "billing.generate",   "access_level": "edit"},
                {"feature_code": "billing.discount",   "access_level": "edit"},
                {"feature_code": "inventory.view",     "access_level": "view"},
                {"feature_code": "analytics.own",      "access_level": "view"},
                {"feature_code": "comms.chat",         "access_level": "edit"},
                {"feature_code": "hotel.rooms",        "access_level": "view"},
                {"feature_code": "hotel.guests",       "access_level": "edit"},
                {"feature_code": "hotel.reservations", "access_level": "edit"},
                {"feature_code": "hotel.checkin",      "access_level": "edit"},
                {"feature_code": "hotel.room_charges", "access_level": "edit"},
                {"feature_code": "hotel.housekeeping", "access_level": "edit"},
            ]
        },
        headers=auth(admin_token)
    )
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        roles = await client.get("/api/v1/roles", headers=auth(admin_token))
        for role in roles.json():
            if role["name"] == "Staff":
                return role
    assert resp.status_code == 201, resp.text
    return resp.json()

@pytest.fixture
async def db():
    conn = await asyncpg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        statement_cache_size=0,
    )
    yield conn
    await conn.close()

@pytest.fixture
async def staff_user(client, admin_token, staff_role, db):
    resp = await client.post(
        "/api/v1/users",
        json={"full_name": "Test Staff",
              "email": "teststaff@testhotel.com",
              "phone": "9800000099"},
        headers=auth(admin_token)
    )
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        row = await db.fetchrow(
            "SELECT id FROM core.users WHERE email = $1",
            "teststaff@testhotel.com"
        )
        user_id = str(row["id"])
    else:
        assert resp.status_code == 201, resp.text
        user_id = resp.json()["user_id"]

    # Assign the staff role
    await client.post(
        "/api/v1/users/assign-role",
        json={"user_id": user_id, "role_template_id": str(staff_role["id"])},
        headers=auth(admin_token)
    )

    from app.utils.password import hash_password
    await db.execute(
        "UPDATE core.users SET password_hash=$1, must_change_password=FALSE WHERE id=$2",
        hash_password("StaffPass@123"), user_id
    )
    return {"user_id": user_id,
            "email": "teststaff@testhotel.com",
            "password": "StaffPass@123"}