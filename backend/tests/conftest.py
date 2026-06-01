import pytest
import asyncpg
from httpx import AsyncClient, ASGITransport
from app.core.config import settings
from app.core import database as db_module


# Reset pool on every test 
@pytest.fixture(autouse=True)
async def reset_pool():
    await db_module.close_pool()
    yield
    await db_module.close_pool()


# Direct DB connection per test 
@pytest.fixture
async def db():
    conn = await asyncpg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
    )
    yield conn
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
async def clean_db_once():
    import asyncpg as apg

    conn = await apg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
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
async def registered_tenant(client):
    resp = await client.post("/api/v1/auth/register", json=TEST_BUSINESS)
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        login = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS["admin_email"],
            "password": TEST_BUSINESS["admin_password"],
            "tenant_slug": "test-hotel-nepal"
        })
        d = login.json()
        return {"schema_name": d["schema_name"],
                "tenant_id": d["user_id"],
                "admin_user_id": d["user_id"]}
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def registered_tenant_b(client):
    resp = await client.post("/api/v1/auth/register", json=TEST_BUSINESS_B)
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        login = await client.post("/api/v1/auth/login", json={
            "email": TEST_BUSINESS_B["admin_email"],
            "password": TEST_BUSINESS_B["admin_password"],
            "tenant_slug": "second-restaurant-nepal"
        })
        d = login.json()
        return {"schema_name": d["schema_name"],
                "tenant_id": d["user_id"],
                "admin_user_id": d["user_id"]}
    assert resp.status_code == 201, resp.text
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
async def staff_user(client, admin_token, db):
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

    from app.utils.password import hash_password
    await db.execute(
        "UPDATE core.users SET password_hash=$1, must_change_password=FALSE WHERE id=$2",
        hash_password("StaffPass@123"), user_id
    )
    return {"user_id": user_id,
            "email": "teststaff@testhotel.com",
            "password": "StaffPass@123"}


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