import pytest
from tests.conftest import TEST_BUSINESS

class TestPasswordStorage:

    async def test_password_stored_as_bcrypt_hash(self, db, registered_tenant):
        """TC-SEC-005: Password stored as bcrypt hash"""
        row = await db.fetchrow(
            """
            SELECT u.password_hash FROM core.users u
            JOIN core.tenants t ON t.id = u.tenant_id
            WHERE t.schema_name = $1 AND u.is_admin = TRUE
            LIMIT 1
            """,
            registered_tenant["schema_name"]
        )
        assert row is not None, "No admin user found"
        assert row["password_hash"].startswith("$2b$")

    async def test_plain_text_password_not_in_db(self, db, registered_tenant):
        """Plain text password never stored"""
        row = await db.fetchrow(
            """
            SELECT u.password_hash FROM core.users u
            JOIN core.tenants t ON t.id = u.tenant_id
            WHERE t.schema_name = $1 AND u.is_admin = TRUE
            LIMIT 1
            """,
            registered_tenant["schema_name"]
        )
        assert row is not None
        assert TEST_BUSINESS["admin_password"] not in row["password_hash"]

    async def test_two_users_same_password_different_hash(self, db, registered_tenant):
        """bcrypt generates unique hash per user even for same password"""
        from app.utils.password import hash_password
        hash1 = hash_password("SamePassword123")
        hash2 = hash_password("SamePassword123")
        assert hash1 != hash2