import pytest
from tests.conftest import TEST_BUSINESS, TEST_BUSINESS_B


class TestRegisterPositive:
    async def test_register_valid_business(self, client):
        """TC-REG-002: Register valid new business returns 201"""
        import uuid
        payload = TEST_BUSINESS.copy()
        payload["business_name"] = f"Test Unique {uuid.uuid4().hex[:6]}"
        payload["admin_email"] = f"admin_{uuid.uuid4().hex[:6]}@test.com"
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "tenant_id" in data
        assert "admin_user_id" in data
        assert "schema_name" in data
        assert data["message"] == "Business registered successfully"

    async def test_tenant_row_created(self, db, registered_tenant):
        """TC-REG-002: Verify tenant row in core.tenants"""
        row = await db.fetchrow(
            "SELECT id, name, type FROM core.tenants WHERE schema_name = $1",
            registered_tenant["schema_name"]
        )
        assert row is not None
        assert row["type"] == TEST_BUSINESS["business_type"]

    async def test_admin_user_created(self, db, registered_tenant):
        """TC-REG-002: Verify admin user in core.users"""
        row = await db.fetchrow(
            """
            SELECT u.id, u.is_admin, u.must_change_password
            FROM core.users u
            JOIN core.tenants t ON t.id = u.tenant_id
            WHERE t.schema_name = $1 AND u.is_admin = TRUE
            """,
            registered_tenant["schema_name"]
        )
        assert row is not None
        assert row["is_admin"] is True
        assert row["must_change_password"] is False

    async def test_register_restaurant_type(self, client, db):
        """TC-REG-003: Register restaurant-only business"""
        payload = TEST_BUSINESS.copy()
        payload["business_name"] = "Pure Restaurant Nepal"
        payload["business_type"] = "restaurant"
        payload["admin_email"] = "purerest@test.com"
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201
        # Cleanup
        await db.execute("DELETE FROM core.tenants WHERE slug = 'pure-restaurant-nepal'")

    async def test_register_hotel_type(self, client, db):
        """TC-REG-004: Register hotel-only business"""
        payload = TEST_BUSINESS.copy()
        payload["business_name"] = "Pure Hotel Nepal"
        payload["business_type"] = "hotel"
        payload["admin_email"] = "purehotel@test.com"
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201
        await db.execute("DELETE FROM core.tenants WHERE slug = 'pure-hotel-nepal'")

    async def test_schema_created_in_db(self, client, db, registered_tenant):
        """TC-REG-002: Verify 75 tables created in tenant schema"""
        schema = registered_tenant["schema_name"]
        count = await db.fetchval(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = $1
            """,
            schema
        )
        assert count == 80

    async def test_special_characters_in_name(self, client, db):
        """TC-REG-014: Business name with special characters"""
        payload = TEST_BUSINESS.copy()
        payload["business_name"] = "Hotel & Spa Kathmandu 2024"
        payload["admin_email"] = "hotelspa@test.com"
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        # Schema name should only have safe characters
        assert " " not in data["schema_name"]
        assert "&" not in data["schema_name"]
        await db.execute("DELETE FROM core.tenants WHERE slug = 'hotel-spa-kathmandu-2024'")


class TestRegisterNegative:

    async def test_duplicate_business_name(self, client):
        """TC-REG-005: Duplicate business name returns 400"""
        resp = await client.post("/api/v1/auth/register", json=TEST_BUSINESS)
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    async def test_invalid_business_type(self, client):
        """TC-REG-006: Invalid business_type returns 400"""
        payload = TEST_BUSINESS.copy()
        payload["business_type"] = "cafe"
        payload["business_name"] = "Unique Cafe Name"
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code in [400, 422]

    async def test_missing_business_name(self, client):
        """TC-REG-007: Missing business_name returns 422"""
        payload = TEST_BUSINESS.copy()
        del payload["business_name"]
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 422

    async def test_missing_admin_email(self, client):
        """TC-REG-008: Missing admin_email returns 422"""
        payload = TEST_BUSINESS.copy()
        del payload["admin_email"]
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 422

    async def test_invalid_email_format(self, client):
        """TC-REG-009: Invalid email format returns 422"""
        payload = TEST_BUSINESS.copy()
        payload["admin_email"] = "notanemail"
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 422

    async def test_empty_business_name(self, client):
        """TC-REG-010: Empty business_name returns 422"""
        payload = TEST_BUSINESS.copy()
        payload["business_name"] = ""
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code in [400, 422]


class TestRegisterSecurity:

    async def test_sql_injection_in_name(self, client, db):
        """TC-REG-011: SQL injection treated as string, no DB damage"""
        payload = TEST_BUSINESS.copy()
        payload["business_name"] = "'; DROP TABLE core.tenants; --"
        payload["admin_email"] = "sqltest@test.com"
        resp = await client.post("/api/v1/auth/register", json=payload)
        # Either succeeds with safe slug or rejects — either way DB is intact
        count = await db.fetchval("SELECT COUNT(*) FROM core.tenants")
        assert count >= 1  # Table still exists

    async def test_xss_in_name_stored_as_plain_text(self, client, db):
        """TC-REG-012: XSS payload stored as plain text"""
        payload = TEST_BUSINESS.copy()
        payload["business_name"] = "<script>alert(1)</script> Hotel"
        payload["admin_email"] = "xsstest@test.com"
        resp = await client.post("/api/v1/auth/register", json=payload)
        if resp.status_code == 201:
            slug = resp.json()["schema_name"]
            row = await db.fetchrow(
                "SELECT name FROM core.tenants WHERE schema_name = $1", slug
            )
            assert "<script>" in row["name"]  # stored as plain text, not executed
            await db.execute("DELETE FROM core.tenants WHERE schema_name = $1", slug)

    async def test_very_long_business_name(self, client):
        """TC-REG-013: Very long string rejected gracefully"""
        payload = TEST_BUSINESS.copy()
        payload["business_name"] = "A" * 500
        payload["admin_email"] = "longname@test.com"
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code in [400, 422]

    async def test_only_spaces_in_name(self, client):
        """TC-REG-015: Business name with only spaces"""
        payload = TEST_BUSINESS.copy()
        payload["business_name"] = "     "
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code in [400, 422]