import pytest
import asyncpg
from datetime import datetime, timezone, timedelta
from uuid import UUID

from tests.conftest import auth, TENANT_SCHEMA, TENANT_SCHEMA_B
from app.core.config import settings


# Helpers 

async def _get_tenant(db, schema: str) -> dict:
    row = await db.fetchrow(
        "SELECT * FROM core.tenants WHERE schema_name = $1", schema
    )
    assert row is not None, f"Tenant not found for schema {schema}"
    return dict(row)


async def _set_status(db, schema: str, status: str, **extra):
    """
    Directly set subscription_status and any extra columns on a tenant.
    Always resets grace_period_ends_at, trial_ends_at, demo_ends_at, suspended_at,
    cancelled_at to NULL unless explicitly passed.
    """
    defaults = {
        "trial_ends_at": None,
        "grace_period_ends_at": None,
        "demo_ends_at": None,
        "suspended_at": None,
        "cancelled_at": None,
        "is_demo": False,
    }
    defaults.update(extra)

    fields = ["subscription_status = $1"]
    values = [status]
    idx = 2
    for key, val in defaults.items():
        fields.append(f"{key} = ${idx}")
        values.append(val)
        idx += 1
    values.append(schema)

    await db.execute(
        f"UPDATE core.tenants SET {', '.join(fields)} WHERE schema_name = ${idx}",
        *values
    )


async def _restore(db, schema: str):
    """Restore tenant to clean active state with high limits."""
    await _set_status(db, schema, "active")
    await db.execute(
        """
        UPDATE core.tenants SET
            subscription_tier = 'max',
            max_outlets    = 999,
            max_staff      = 999,
            max_menu_items = 9999
        WHERE schema_name = $1
        """,
        schema
    )


async def _clear_receipts(db, schema: str):
    tenant = await db.fetchrow(
        "SELECT id FROM core.tenants WHERE schema_name = $1", schema
    )
    await db.execute(
        "DELETE FROM core.payment_receipts WHERE tenant_id = $1",
        tenant["id"]
    )


async def _clear_events(db, schema: str, event_type: str = None):
    tenant = await db.fetchrow(
        "SELECT id FROM core.tenants WHERE schema_name = $1", schema
    )
    if event_type:
        await db.execute(
            "DELETE FROM core.subscription_events WHERE tenant_id = $1 AND event_type = $2",
            tenant["id"], event_type
        )
    else:
        await db.execute(
            "DELETE FROM core.subscription_events WHERE tenant_id = $1",
            tenant["id"]
        )


def _receipt_payload(schema: str, ref: str = "TXN-TEST-001", plan: str = "pro"):
    return {
        "plan_code": plan,
        "amount_npr": "2500.00",
        "payment_reference": ref,
        "receipt_key": f"payment-receipts/{schema}/{ref}.jpg",
        "receipt_url": f"https://r2.example.com/payment-receipts/{schema}/{ref}.jpg",
    }


# SECTION 1 — TRIAL ON REGISTRATION

class TestTrialOnRegistration:
    """
    Verify that registering a new tenant correctly initialises trial state.
    Uses a fresh registration per test to avoid contaminating the shared
    test tenants which are set to active by the migration.
    """

    async def _register_fresh(self, client) -> dict:
        import uuid
        uid = uuid.uuid4().hex[:6]
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "business_name": f"Trial Biz {uid}",
                "business_type": "restaurant",
                "business_email": f"biz{uid}@trial.com",
                "business_phone": "9800000099",
                "city": "Kathmandu",
                "admin_full_name": "Trial Admin",
                "admin_email": f"admin{uid}@trial.com",
                "admin_password": "TestPass@123",
                "admin_phone": "9800000099",
            }
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    async def _cleanup(self, schema: str):
        conn = await asyncpg.connect(
            host=settings.DB_HOST, port=settings.DB_PORT,
            user=settings.DB_USER, password=settings.DB_PASSWORD,
            database=settings.DB_NAME, statement_cache_size=0,
        )
        try:
            t = await conn.fetchrow(
                "SELECT id FROM core.tenants WHERE schema_name = $1", schema
            )
            if t:
                await conn.execute(
                    "DELETE FROM core.subscription_events WHERE tenant_id = $1",
                    t["id"]
                )
                await conn.execute(
                    "DELETE FROM core.payment_receipts WHERE tenant_id = $1",
                    t["id"]
                )
                await conn.execute(
                    "DELETE FROM core.refresh_tokens WHERE user_id IN "
                    "(SELECT id FROM core.users WHERE tenant_id = $1)",
                    t["id"]
                )
                await conn.execute(
                    "DELETE FROM core.users WHERE tenant_id = $1", t["id"]
                )
                await conn.execute(
                    f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'
                )
                await conn.execute(
                    "DELETE FROM core.tenants WHERE id = $1", t["id"]
                )
        finally:
            await conn.close()

    async def test_new_tenant_has_trialing_status(self, client):
        result = await self._register_fresh(client)
        schema = result["schema_name"]
        try:
            conn = await asyncpg.connect(
                host=settings.DB_HOST, port=settings.DB_PORT,
                user=settings.DB_USER, password=settings.DB_PASSWORD,
                database=settings.DB_NAME, statement_cache_size=0,
            )
            try:
                t = await conn.fetchrow(
                    "SELECT subscription_status FROM core.tenants WHERE schema_name = $1",
                    schema
                )
                assert t["subscription_status"] == "trialing"
            finally:
                await conn.close()
        finally:
            await self._cleanup(schema)

    async def test_new_tenant_trial_on_pro_plan(self, client):
        result = await self._register_fresh(client)
        schema = result["schema_name"]
        try:
            conn = await asyncpg.connect(
                host=settings.DB_HOST, port=settings.DB_PORT,
                user=settings.DB_USER, password=settings.DB_PASSWORD,
                database=settings.DB_NAME, statement_cache_size=0,
            )
            try:
                t = await conn.fetchrow(
                    "SELECT subscription_tier FROM core.tenants WHERE schema_name = $1",
                    schema
                )
                assert t["subscription_tier"] == "pro"
            finally:
                await conn.close()
        finally:
            await self._cleanup(schema)

    async def test_new_tenant_trial_ends_at_is_14_days(self, client):
        result = await self._register_fresh(client)
        schema = result["schema_name"]
        try:
            conn = await asyncpg.connect(
                host=settings.DB_HOST, port=settings.DB_PORT,
                user=settings.DB_USER, password=settings.DB_PASSWORD,
                database=settings.DB_NAME, statement_cache_size=0,
            )
            try:
                t = await conn.fetchrow(
                    "SELECT trial_ends_at, trial_days FROM core.tenants WHERE schema_name = $1",
                    schema
                )
                assert t["trial_ends_at"] is not None
                assert t["trial_days"] == 14
                now = datetime.now(timezone.utc)
                expected = now + timedelta(days=14)
                diff = abs((t["trial_ends_at"] - expected).total_seconds())
                assert diff < 60
            finally:
                await conn.close()
        finally:
            await self._cleanup(schema)

    async def test_new_tenant_current_period_start_set(self, client):
        result = await self._register_fresh(client)
        schema = result["schema_name"]
        try:
            conn = await asyncpg.connect(
                host=settings.DB_HOST, port=settings.DB_PORT,
                user=settings.DB_USER, password=settings.DB_PASSWORD,
                database=settings.DB_NAME, statement_cache_size=0,
            )
            try:
                t = await conn.fetchrow(
                    "SELECT current_period_start FROM core.tenants WHERE schema_name = $1",
                    schema
                )
                assert t["current_period_start"] is not None
            finally:
                await conn.close()
        finally:
            await self._cleanup(schema)

    async def test_new_tenant_gets_pro_plan_limits(self, client):
        result = await self._register_fresh(client)
        schema = result["schema_name"]
        try:
            conn = await asyncpg.connect(
                host=settings.DB_HOST, port=settings.DB_PORT,
                user=settings.DB_USER, password=settings.DB_PASSWORD,
                database=settings.DB_NAME, statement_cache_size=0,
            )
            try:
                t = await conn.fetchrow(
                    "SELECT max_outlets, max_staff, max_menu_items FROM core.tenants WHERE schema_name = $1",
                    schema
                )
                assert t["max_outlets"] == 3
                assert t["max_staff"] == 30
                assert t["max_menu_items"] == 500
            finally:
                await conn.close()
        finally:
            await self._cleanup(schema)

    async def test_registration_inserts_trial_started_event(self, client):
        result = await self._register_fresh(client)
        schema = result["schema_name"]
        try:
            conn = await asyncpg.connect(
                host=settings.DB_HOST, port=settings.DB_PORT,
                user=settings.DB_USER, password=settings.DB_PASSWORD,
                database=settings.DB_NAME, statement_cache_size=0,
            )
            try:
                t = await conn.fetchrow(
                    "SELECT id FROM core.tenants WHERE schema_name = $1", schema
                )
                events = await conn.fetch(
                    "SELECT * FROM core.subscription_events WHERE tenant_id = $1",
                    t["id"]
                )
                assert len(events) >= 1
                types = [e["event_type"] for e in events]
                assert "trial_started" in types
            finally:
                await conn.close()
        finally:
            await self._cleanup(schema)

    async def test_trial_started_event_has_correct_fields(self, client):
        result = await self._register_fresh(client)
        schema = result["schema_name"]
        try:
            conn = await asyncpg.connect(
                host=settings.DB_HOST, port=settings.DB_PORT,
                user=settings.DB_USER, password=settings.DB_PASSWORD,
                database=settings.DB_NAME, statement_cache_size=0,
            )
            try:
                t = await conn.fetchrow(
                    "SELECT id FROM core.tenants WHERE schema_name = $1", schema
                )
                event = await conn.fetchrow(
                    "SELECT * FROM core.subscription_events WHERE tenant_id = $1 AND event_type = 'trial_started'",
                    t["id"]
                )
                assert event is not None
                assert event["to_status"] == "trialing"
                assert event["to_tier"] == "pro"
                assert event["period_start"] is not None
                assert event["period_end"] is not None
                assert event["created_by"] == "system"
            finally:
                await conn.close()
        finally:
            await self._cleanup(schema)


# SECTION 2 — GET /subscription

class TestGetSubscription:

    async def test_admin_can_get_subscription(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_response_has_status_field(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token)
        )
        assert "status" in resp.json()

    async def test_response_has_tier_field(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token)
        )
        assert "tier" in resp.json()

    async def test_response_has_is_demo_field(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token)
        )
        assert "is_demo" in resp.json()

    async def test_response_has_usage_field(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token)
        )
        assert "usage" in resp.json()

    async def test_usage_has_outlets(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token)
        )
        usage = resp.json()["usage"]
        assert "outlets" in usage
        assert "used" in usage["outlets"]
        assert "limit" in usage["outlets"]

    async def test_usage_has_staff(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token)
        )
        usage = resp.json()["usage"]
        assert "staff" in usage
        assert "used" in usage["staff"]
        assert "limit" in usage["staff"]

    async def test_usage_has_menu_items(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token)
        )
        usage = resp.json()["usage"]
        assert "menu_items" in usage
        assert "used" in usage["menu_items"]
        assert "limit" in usage["menu_items"]

    async def test_usage_outlets_used_is_integer(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token)
        )
        assert isinstance(resp.json()["usage"]["outlets"]["used"], int)

    async def test_plan_info_included(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token)
        )
        data = resp.json()
        assert "plan" in data
        if data["plan"]:
            assert "plan_code" in data["plan"]
            assert "display_name" in data["plan"]

    async def test_trialing_shows_trial_days_remaining(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(
            db, TENANT_SCHEMA, "trialing",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        try:
            resp = await client.get(
                "/api/v1/subscription", headers=auth(admin_token)
            )
            data = resp.json()
            assert data["status"] == "trialing"
            assert data["trial_days_remaining"] is not None
            assert 0 <= data["trial_days_remaining"] <= 7
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_past_due_shows_grace_days_remaining(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(
            db, TENANT_SCHEMA, "past_due",
            grace_period_ends_at=datetime.now(timezone.utc) + timedelta(days=3)
        )
        try:
            resp = await client.get(
                "/api/v1/subscription", headers=auth(admin_token)
            )
            data = resp.json()
            assert data["status"] == "past_due"
            assert data["grace_period_days_remaining"] is not None
            assert 0 <= data["grace_period_days_remaining"] <= 3
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_staff_cannot_access_subscription(
        self, client, staff_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription", headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_access_subscription(
        self, client, registered_tenant
    ):
        resp = await client.get("/api/v1/subscription")
        assert resp.status_code == 403

    async def test_expired_token_cannot_access_subscription(
        self, client, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription",
            headers=auth("totally.invalid.token")
        )
        assert resp.status_code == 401

    async def test_wrong_schema_token_cannot_access_subscription(
        self, client, admin_token_b, registered_tenant, registered_tenant_b
    ):
        # Tenant B's token should return tenant B's subscription not A's
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token_b)
        )
        assert resp.status_code == 200
        # Just confirm it returns successfully — isolation tested in section 8


# SECTION 3 — GET /subscription/plans

class TestGetPlans:

    async def test_any_authed_user_can_get_plans(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/plans", headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_staff_can_get_plans(
        self, client, staff_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/plans", headers=auth(staff_token)
        )
        assert resp.status_code == 200

    async def test_plans_returns_list(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/plans", headers=auth(admin_token)
        )
        assert isinstance(resp.json(), list)

    async def test_all_four_plans_present(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/plans", headers=auth(admin_token)
        )
        codes = {p["plan_code"] for p in resp.json()}
        assert "ez" in codes
        assert "pro" in codes
        assert "max" in codes
        assert "enterprise" in codes

    async def test_plans_have_plan_code(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/plans", headers=auth(admin_token)
        )
        for plan in resp.json():
            assert "plan_code" in plan

    async def test_plans_have_display_name(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/plans", headers=auth(admin_token)
        )
        for plan in resp.json():
            assert "display_name" in plan

    async def test_plans_have_price_field(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/plans", headers=auth(admin_token)
        )
        for plan in resp.json():
            assert "price_monthly_npr" in plan

    async def test_unauthenticated_cannot_get_plans(
        self, client, registered_tenant
    ):
        resp = await client.get("/api/v1/subscription/plans")
        assert resp.status_code == 403

    async def test_invalid_token_cannot_get_plans(
        self, client, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/plans",
            headers=auth("bad.token.here")
        )
        assert resp.status_code == 401


# SECTION 4 — GET /subscription/history

class TestGetHistory:

    async def test_admin_can_get_history(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/history", headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_history_returns_list(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/history", headers=auth(admin_token)
        )
        assert isinstance(resp.json(), list)

    async def test_history_events_have_id(
        self, client, admin_token, registered_tenant, db
    ):
        tenant = await _get_tenant(db, TENANT_SCHEMA)
        await db.execute(
            """
            INSERT INTO core.subscription_events
                (tenant_id, event_type, from_status, to_status, created_by)
            VALUES ($1, 'test_history_event', 'active', 'suspended', 'test')
            """,
            tenant["id"]
        )
        try:
            resp = await client.get(
                "/api/v1/subscription/history", headers=auth(admin_token)
            )
            events = resp.json()
            assert len(events) >= 1
            assert "id" in events[0]
        finally:
            await _clear_events(db, TENANT_SCHEMA, "test_history_event")

    async def test_history_events_have_event_type(
        self, client, admin_token, registered_tenant, db
    ):
        tenant = await _get_tenant(db, TENANT_SCHEMA)
        await db.execute(
            """
            INSERT INTO core.subscription_events
                (tenant_id, event_type, created_by)
            VALUES ($1, 'test_event_type', 'test')
            """,
            tenant["id"]
        )
        try:
            resp = await client.get(
                "/api/v1/subscription/history", headers=auth(admin_token)
            )
            events = resp.json()
            assert any(e["event_type"] == "test_event_type" for e in events)
        finally:
            await _clear_events(db, TENANT_SCHEMA, "test_event_type")

    async def test_history_events_have_created_at(
        self, client, admin_token, registered_tenant, db
    ):
        tenant = await _get_tenant(db, TENANT_SCHEMA)
        await db.execute(
            "INSERT INTO core.subscription_events (tenant_id, event_type, created_by) VALUES ($1, 'ts_event', 'test')",
            tenant["id"]
        )
        try:
            resp = await client.get(
                "/api/v1/subscription/history", headers=auth(admin_token)
            )
            for event in resp.json():
                assert "created_at" in event
        finally:
            await _clear_events(db, TENANT_SCHEMA, "ts_event")

    async def test_history_events_have_created_by(
        self, client, admin_token, registered_tenant, db
    ):
        tenant = await _get_tenant(db, TENANT_SCHEMA)
        await db.execute(
            "INSERT INTO core.subscription_events (tenant_id, event_type, created_by) VALUES ($1, 'cb_event', 'test')",
            tenant["id"]
        )
        try:
            resp = await client.get(
                "/api/v1/subscription/history", headers=auth(admin_token)
            )
            for event in resp.json():
                assert "created_by" in event
        finally:
            await _clear_events(db, TENANT_SCHEMA, "cb_event")

    async def test_history_ordered_newest_first(
        self, client, admin_token, registered_tenant, db
    ):
        tenant = await _get_tenant(db, TENANT_SCHEMA)
        await db.execute(
            """
            INSERT INTO core.subscription_events (tenant_id, event_type, created_by)
            VALUES ($1, 'event_old', 'test'), ($1, 'event_new', 'test')
            """,
            tenant["id"]
        )
        try:
            resp = await client.get(
                "/api/v1/subscription/history", headers=auth(admin_token)
            )
            events = resp.json()
            if len(events) >= 2:
                first_dt = datetime.fromisoformat(
                    events[0]["created_at"].replace("Z", "+00:00")
                )
                second_dt = datetime.fromisoformat(
                    events[1]["created_at"].replace("Z", "+00:00")
                )
                assert first_dt >= second_dt
        finally:
            await _clear_events(db, TENANT_SCHEMA, "event_old")
            await _clear_events(db, TENANT_SCHEMA, "event_new")

    async def test_staff_cannot_access_history(
        self, client, staff_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/history", headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_access_history(
        self, client, registered_tenant
    ):
        resp = await client.get("/api/v1/subscription/history")
        assert resp.status_code == 403

    async def test_invalid_token_cannot_access_history(
        self, client, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/history",
            headers=auth("bad.token.value")
        )
        assert resp.status_code == 401


# SECTION 5 — GET /subscription/renew

class TestGetRenewInfo:

    async def test_admin_can_get_renew_info(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/renew", headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_renew_info_has_plan_code(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/renew", headers=auth(admin_token)
        )
        assert "plan_code" in resp.json()

    async def test_renew_info_has_display_name(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/renew", headers=auth(admin_token)
        )
        assert "plan_display_name" in resp.json()

    async def test_renew_info_has_qr_url(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/renew", headers=auth(admin_token)
        )
        assert "qr_image_url" in resp.json()

    async def test_renew_info_has_payment_instructions(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/renew", headers=auth(admin_token)
        )
        assert "payment_instructions" in resp.json()
        assert len(resp.json()["payment_instructions"]) > 0

    async def test_renew_info_has_reference_format(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/renew", headers=auth(admin_token)
        )
        assert "reference_format" in resp.json()

    async def test_renew_info_shows_tenant_plan(
        self, client, admin_token, registered_tenant, db
    ):
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'pro' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        try:
            resp = await client.get(
                "/api/v1/subscription/renew", headers=auth(admin_token)
            )
            assert resp.json()["plan_code"] == "pro"
        finally:
            await db.execute(
                "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_staff_cannot_access_renew(
        self, client, staff_token, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/renew", headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_access_renew(
        self, client, registered_tenant
    ):
        resp = await client.get("/api/v1/subscription/renew")
        assert resp.status_code == 403

    async def test_invalid_token_cannot_access_renew(
        self, client, registered_tenant
    ):
        resp = await client.get(
            "/api/v1/subscription/renew",
            headers=auth("not.a.real.token")
        )
        assert resp.status_code == 401


# SECTION 6 — POST /subscription/payment-receipt/upload-url

class TestReceiptUploadUrl:

    async def test_admin_can_get_upload_url(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=receipt.jpg",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_upload_url_has_upload_url_field(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=receipt.jpg",
            headers=auth(admin_token)
        )
        assert "upload_url" in resp.json()

    async def test_upload_url_has_key_field(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=receipt.jpg",
            headers=auth(admin_token)
        )
        assert "key" in resp.json()

    async def test_upload_url_has_public_url_field(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=receipt.jpg",
            headers=auth(admin_token)
        )
        assert "public_url" in resp.json()

    async def test_key_contains_tenant_schema(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=receipt.jpg",
            headers=auth(admin_token)
        )
        assert TENANT_SCHEMA in resp.json()["key"]

    async def test_key_starts_with_payment_receipts_prefix(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=receipt.jpg",
            headers=auth(admin_token)
        )
        assert resp.json()["key"].startswith("payment-receipts/")

    async def test_key_has_jpg_extension(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=receipt.jpg",
            headers=auth(admin_token)
        )
        assert resp.json()["key"].endswith(".jpg")

    async def test_key_has_png_extension_when_png_uploaded(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=receipt.png",
            headers=auth(admin_token)
        )
        assert resp.json()["key"].endswith(".png")

    async def test_each_call_generates_unique_key(
        self, client, admin_token, registered_tenant
    ):
        resp1 = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=r.jpg",
            headers=auth(admin_token)
        )
        resp2 = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=r.jpg",
            headers=auth(admin_token)
        )
        assert resp1.json()["key"] != resp2.json()["key"]

    async def test_staff_cannot_get_upload_url(
        self, client, staff_token, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=receipt.jpg",
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_get_upload_url(
        self, client, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=receipt.jpg"
        )
        assert resp.status_code == 403

    async def test_invalid_token_cannot_get_upload_url(
        self, client, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt/upload-url?filename=receipt.jpg",
            headers=auth("invalid.token.here")
        )
        assert resp.status_code == 401


# SECTION 7 — POST /subscription/payment-receipt

class TestSubmitPaymentReceipt:

    async def test_admin_can_submit_receipt(
        self, client, admin_token, registered_tenant, db
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-SUBMIT-001"),
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        await _clear_receipts(db, TENANT_SCHEMA)

    async def test_receipt_stored_in_db(
        self, client, admin_token, registered_tenant, db
    ):
        await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-DB-001"),
            headers=auth(admin_token)
        )
        tenant = await _get_tenant(db, TENANT_SCHEMA)
        receipt = await db.fetchrow(
            "SELECT * FROM core.payment_receipts WHERE tenant_id = $1 AND payment_reference = $2",
            tenant["id"], "TXN-DB-001"
        )
        assert receipt is not None
        await _clear_receipts(db, TENANT_SCHEMA)

    async def test_receipt_has_pending_status(
        self, client, admin_token, registered_tenant, db
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-PEND-001"),
            headers=auth(admin_token)
        )
        assert resp.json()["status"] == "pending_verification"
        await _clear_receipts(db, TENANT_SCHEMA)

    async def test_receipt_stores_correct_plan_code(
        self, client, admin_token, registered_tenant, db
    ):
        await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-PLAN-001", plan="pro"),
            headers=auth(admin_token)
        )
        tenant = await _get_tenant(db, TENANT_SCHEMA)
        receipt = await db.fetchrow(
            "SELECT plan_code FROM core.payment_receipts WHERE tenant_id = $1 AND payment_reference = $2",
            tenant["id"], "TXN-PLAN-001"
        )
        assert receipt["plan_code"] == "pro"
        await _clear_receipts(db, TENANT_SCHEMA)

    async def test_receipt_stores_correct_amount(
        self, client, admin_token, registered_tenant, db
    ):
        await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-AMT-001"),
            headers=auth(admin_token)
        )
        tenant = await _get_tenant(db, TENANT_SCHEMA)
        receipt = await db.fetchrow(
            "SELECT amount_npr FROM core.payment_receipts WHERE tenant_id = $1 AND payment_reference = $2",
            tenant["id"], "TXN-AMT-001"
        )
        assert float(receipt["amount_npr"]) == 2500.00
        await _clear_receipts(db, TENANT_SCHEMA)

    async def test_receipt_stores_correct_reference(
        self, client, admin_token, registered_tenant, db
    ):
        await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-REF-001"),
            headers=auth(admin_token)
        )
        tenant = await _get_tenant(db, TENANT_SCHEMA)
        receipt = await db.fetchrow(
            "SELECT payment_reference FROM core.payment_receipts WHERE tenant_id = $1",
            tenant["id"]
        )
        assert receipt["payment_reference"] == "TXN-REF-001"
        await _clear_receipts(db, TENANT_SCHEMA)

    async def test_receipt_stores_receipt_key(
        self, client, admin_token, registered_tenant, db
    ):
        await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-KEY-001"),
            headers=auth(admin_token)
        )
        tenant = await _get_tenant(db, TENANT_SCHEMA)
        receipt = await db.fetchrow(
            "SELECT receipt_key FROM core.payment_receipts WHERE tenant_id = $1",
            tenant["id"]
        )
        assert receipt["receipt_key"] is not None
        assert len(receipt["receipt_key"]) > 0
        await _clear_receipts(db, TENANT_SCHEMA)

    async def test_cannot_submit_while_pending_receipt_exists(
        self, client, admin_token, registered_tenant, db
    ):
        await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-DUP-001"),
            headers=auth(admin_token)
        )
        resp2 = await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-DUP-002"),
            headers=auth(admin_token)
        )
        assert resp2.status_code == 400
        await _clear_receipts(db, TENANT_SCHEMA)

    async def test_duplicate_rejection_message_mentions_pending(
        self, client, admin_token, registered_tenant, db
    ):
        await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-MSG-001"),
            headers=auth(admin_token)
        )
        resp2 = await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-MSG-002"),
            headers=auth(admin_token)
        )
        assert "pending" in resp2.json()["detail"].lower()
        await _clear_receipts(db, TENANT_SCHEMA)

    async def test_can_submit_after_previous_confirmed(
        self, client, admin_token, registered_tenant, db
    ):
        await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-CONF-001"),
            headers=auth(admin_token)
        )
        # Manually mark as confirmed
        tenant = await _get_tenant(db, TENANT_SCHEMA)
        await db.execute(
            """
            UPDATE core.payment_receipts
            SET status = 'confirmed', confirmed_at = NOW(), confirmed_by = 'test'
            WHERE tenant_id = $1
            """,
            tenant["id"]
        )
        # Should now be able to submit a new one
        resp2 = await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-CONF-002"),
            headers=auth(admin_token)
        )
        assert resp2.status_code == 201
        await _clear_receipts(db, TENANT_SCHEMA)

    async def test_can_submit_after_previous_rejected(
        self, client, admin_token, registered_tenant, db
    ):
        await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-REJ-001"),
            headers=auth(admin_token)
        )
        tenant = await _get_tenant(db, TENANT_SCHEMA)
        await db.execute(
            """
            UPDATE core.payment_receipts
            SET status = 'rejected', rejection_reason = 'test rejection'
            WHERE tenant_id = $1
            """,
            tenant["id"]
        )
        resp2 = await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-REJ-002"),
            headers=auth(admin_token)
        )
        assert resp2.status_code == 201
        await _clear_receipts(db, TENANT_SCHEMA)

    async def test_staff_cannot_submit_receipt(
        self, client, staff_token, registered_tenant, db
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-STAFF-001"),
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_submit_receipt(
        self, client, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-NOAUTH-001")
        )
        assert resp.status_code == 403

    async def test_invalid_token_cannot_submit_receipt(
        self, client, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-BADTOKEN-001"),
            headers=auth("fake.jwt.token")
        )
        assert resp.status_code == 401

    async def test_missing_plan_code_rejected(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt",
            data={
                "amount_npr": "2500.00",
                "payment_reference": "TXN-MISSING-001",
                "receipt_key": "payment-receipts/test/f.jpg",
                "receipt_url": "https://r2.example.com/f.jpg",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_missing_reference_rejected(
        self, client, admin_token, registered_tenant
    ):
        resp = await client.post(
            "/api/v1/subscription/payment-receipt",
            data={
                "plan_code": "pro",
                "amount_npr": "2500.00",
                "receipt_key": "payment-receipts/test/f.jpg",
                "receipt_url": "https://r2.example.com/f.jpg",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422


# SECTION 8 — SUBSCRIPTION STATE ENFORCEMENT

class TestSubscriptionEnforcement:
    """
    Verify that subscription state is enforced on every require_feature endpoint.
    Uses GET /api/v1/menu/categories as the canonical feature-gated endpoint.
    """

    async def test_active_tenant_can_access_features(
        self, client, admin_token, registered_tenant, db
    ):
        await _restore(db, TENANT_SCHEMA)
        resp = await client.get(
            "/api/v1/menu/categories", headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_trialing_within_period_can_access(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(
            db, TENANT_SCHEMA, "trialing",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.status_code == 200
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_trialing_expired_blocks_access(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(
            db, TENANT_SCHEMA, "trialing",
            trial_ends_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.status_code == 402
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_trialing_expired_returns_trial_expired_code(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(
            db, TENANT_SCHEMA, "trialing",
            trial_ends_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.json()["detail"]["code"] == "trial_expired"
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_trial_expired_response_has_action_field(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(
            db, TENANT_SCHEMA, "trialing",
            trial_ends_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert "action" in resp.json()["detail"]
            assert resp.json()["detail"]["action"] == "renew"
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_past_due_within_grace_allows_access(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(
            db, TENANT_SCHEMA, "past_due",
            grace_period_ends_at=datetime.now(timezone.utc) + timedelta(days=3)
        )
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.status_code == 200
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_past_due_grace_expired_blocks_access(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(
            db, TENANT_SCHEMA, "past_due",
            grace_period_ends_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.status_code == 402
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_past_due_grace_expired_returns_grace_expired_code(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(
            db, TENANT_SCHEMA, "past_due",
            grace_period_ends_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.json()["detail"]["code"] == "grace_expired"
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_suspended_tenant_blocks_access(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(db, TENANT_SCHEMA, "suspended")
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.status_code == 402
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_suspended_returns_suspended_code(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(db, TENANT_SCHEMA, "suspended")
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.json()["detail"]["code"] == "suspended"
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_suspended_response_has_message(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(db, TENANT_SCHEMA, "suspended")
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert "message" in resp.json()["detail"]
            assert len(resp.json()["detail"]["message"]) > 0
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_suspended_response_has_action(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(db, TENANT_SCHEMA, "suspended")
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert "action" in resp.json()["detail"]
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_cancelled_tenant_blocks_access(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(db, TENANT_SCHEMA, "cancelled")
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.status_code == 402
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_cancelled_returns_cancelled_code(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(db, TENANT_SCHEMA, "cancelled")
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.json()["detail"]["code"] == "cancelled"
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_cancelled_response_action_is_contact(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(db, TENANT_SCHEMA, "cancelled")
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.json()["detail"]["action"] == "contact"
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_demo_within_period_allows_access(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(
            db, TENANT_SCHEMA, "demo",
            is_demo=True,
            demo_ends_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.status_code == 200
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_demo_expired_blocks_access(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(
            db, TENANT_SCHEMA, "demo",
            is_demo=True,
            demo_ends_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.status_code == 402
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_demo_expired_returns_demo_expired_code(
        self, client, admin_token, registered_tenant, db
    ):
        await _set_status(
            db, TENANT_SCHEMA, "demo",
            is_demo=True,
            demo_ends_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.json()["detail"]["code"] == "demo_expired"
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_suspended_tenant_can_still_view_subscription_endpoint(
        self, client, admin_token, registered_tenant, db
    ):
        """
        /api/v1/subscription uses get_current_admin not require_feature
        so it must remain accessible even when suspended.
        Tenants need to know their status to take action.
        """
        await _set_status(db, TENANT_SCHEMA, "suspended")
        try:
            resp = await client.get(
                "/api/v1/subscription", headers=auth(admin_token)
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "suspended"
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_suspended_tenant_can_still_view_renew_endpoint(
        self, client, admin_token, registered_tenant, db
    ):
        """Tenant must be able to get QR code to pay even when suspended."""
        await _set_status(db, TENANT_SCHEMA, "suspended")
        try:
            resp = await client.get(
                "/api/v1/subscription/renew", headers=auth(admin_token)
            )
            assert resp.status_code == 200
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_suspended_tenant_can_submit_payment_receipt(
        self, client, admin_token, registered_tenant, db
    ):
        """Tenant must be able to submit payment even when suspended."""
        await _set_status(db, TENANT_SCHEMA, "suspended")
        try:
            resp = await client.post(
                "/api/v1/subscription/payment-receipt",
                data=_receipt_payload(TENANT_SCHEMA, "TXN-SUSP-PAY-001"),
                headers=auth(admin_token)
            )
            assert resp.status_code == 201
        finally:
            await _clear_receipts(db, TENANT_SCHEMA)
            await _restore(db, TENANT_SCHEMA)

    async def test_login_not_blocked_by_subscription_status(
        self, client, registered_tenant, db
    ):
        """Login must work regardless of subscription status."""
        await _set_status(db, TENANT_SCHEMA, "suspended")
        try:
            from tests.conftest import TEST_BUSINESS
            resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": TEST_BUSINESS["admin_email"],
                    "password": TEST_BUSINESS["admin_password"],
                    "tenant_slug": "test-hotel-nepal"
                }
            )
            assert resp.status_code == 200
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_subscription_enforcement_applies_to_multiple_endpoints(
        self, client, admin_token, registered_tenant, db
    ):
        """Verify enforcement is not limited to one endpoint."""
        await _set_status(db, TENANT_SCHEMA, "suspended")
        try:
            endpoints = [
                "/api/v1/menu/categories",
                "/api/v1/orders",
                "/api/v1/billing/bills",
                "/api/v1/inventory/suppliers",
            ]
            for endpoint in endpoints:
                resp = await client.get(
                    endpoint, headers=auth(admin_token)
                )
                assert resp.status_code == 402, \
                    f"Expected 402 for {endpoint}, got {resp.status_code}"
        finally:
            await _restore(db, TENANT_SCHEMA)


# SECTION 9 — PLAN FEATURE RESTRICTIONS (DB-DRIVEN)

class TestPlanFeatureRestrictions:

    async def test_ez_plan_blocks_hotel_checkin(
        self, client, admin_token, registered_tenant, db
    ):
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'ez' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        try:
            resp = await client.get(
                "/api/v1/hotel/reservations", headers=auth(admin_token)
            )
            assert resp.status_code == 403
        finally:
            await db.execute(
                "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_ez_plan_blocks_hotel_rooms(
        self, client, admin_token, registered_tenant, db
    ):
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'ez' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        try:
            resp = await client.get(
                "/api/v1/hotel/room-types", headers=auth(admin_token)
            )
            assert resp.status_code == 403
        finally:
            await db.execute(
                "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_ez_plan_blocks_hotel_guests(
        self, client, admin_token, registered_tenant, db
    ):
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'ez' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        try:
            resp = await client.get(
                "/api/v1/hotel/guests", headers=auth(admin_token)
            )
            assert resp.status_code == 403
        finally:
            await db.execute(
                "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_ez_plan_still_allows_menu_access(
        self, client, admin_token, registered_tenant, db
    ):
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'ez' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        try:
            resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp.status_code == 200
        finally:
            await db.execute(
                "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_ez_plan_still_allows_order_access(
        self, client, admin_token, registered_tenant, db
    ):
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'ez' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        try:
            resp = await client.get(
                "/api/v1/orders", headers=auth(admin_token)
            )
            assert resp.status_code == 200
        finally:
            await db.execute(
                "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_ez_plan_still_allows_billing_access(
        self, client, admin_token, registered_tenant, db
    ):
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'ez' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        try:
            resp = await client.get(
                "/api/v1/billing/bills", headers=auth(admin_token)
            )
            assert resp.status_code == 200
        finally:
            await db.execute(
                "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_pro_plan_allows_hotel_features(
        self, client, admin_token, registered_tenant, db
    ):
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'pro' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        try:
            resp = await client.get(
                "/api/v1/hotel/room-types", headers=auth(admin_token)
            )
            assert resp.status_code == 200
        finally:
            await db.execute(
                "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_max_plan_allows_all_features(
        self, client, admin_token, registered_tenant, db
    ):
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        resp = await client.get(
            "/api/v1/hotel/room-types", headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_403_detail_mentions_plan(
        self, client, admin_token, registered_tenant, db
    ):
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'ez' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        try:
            resp = await client.get(
                "/api/v1/hotel/room-types", headers=auth(admin_token)
            )
            assert "plan" in resp.json()["detail"].lower()
        finally:
            await db.execute(
                "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_plan_feature_restriction_is_db_driven_not_hardcoded(
        self, client, admin_token, registered_tenant, db
    ):
        """
        Add a new restriction via DB and verify it takes effect immediately
        without any code change. This proves the restriction is DB-driven.
        """
        await db.execute(
            """
            INSERT INTO core.plan_features (plan_code, feature_code, is_included)
            VALUES ('max', 'inventory.view', FALSE)
            ON CONFLICT (plan_code, feature_code) DO UPDATE SET is_included = FALSE
            """
        )
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        try:
            resp = await client.get(
                "/api/v1/inventory/suppliers", headers=auth(admin_token)
            )
            assert resp.status_code == 403
        finally:
            await db.execute(
                "DELETE FROM core.plan_features WHERE plan_code = 'max' AND feature_code = 'inventory.view'"
            )

    async def test_removing_db_restriction_restores_access(
        self, client, admin_token, registered_tenant, db
    ):
        """
        Add restriction, verify it blocks, remove it, verify access restored.
        Proves DB drives the check with no caching issues.
        """
        await db.execute(
            """
            INSERT INTO core.plan_features (plan_code, feature_code, is_included)
            VALUES ('max', 'inventory.view', FALSE)
            ON CONFLICT (plan_code, feature_code) DO UPDATE SET is_included = FALSE
            """
        )
        resp_blocked = await client.get(
            "/api/v1/inventory/suppliers", headers=auth(admin_token)
        )
        assert resp_blocked.status_code == 403

        await db.execute(
            "DELETE FROM core.plan_features WHERE plan_code = 'max' AND feature_code = 'inventory.view'"
        )

        resp_allowed = await client.get(
            "/api/v1/inventory/suppliers", headers=auth(admin_token)
        )
        assert resp_allowed.status_code == 200


# SECTION 10 — USAGE LIMIT ENFORCEMENT

class TestUsageLimitEnforcement:

    async def test_outlet_limit_blocks_creation_when_at_limit(
        self, client, admin_token, registered_tenant, db
    ):
        # Already have 1 default outlet — set limit to 1
        await db.execute(
            "UPDATE core.tenants SET max_outlets = 1 WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        try:
            resp = await client.post(
                "/api/v1/outlets",
                json={"name": "Blocked Outlet", "type": "restaurant"},
                headers=auth(admin_token)
            )
            assert resp.status_code == 403
        finally:
            await db.execute(
                "UPDATE core.tenants SET max_outlets = 999 WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_outlet_limit_error_mentions_outlet_limit(
        self, client, admin_token, registered_tenant, db
    ):
        await db.execute(
            "UPDATE core.tenants SET max_outlets = 1 WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        try:
            resp = await client.post(
                "/api/v1/outlets",
                json={"name": "Blocked Outlet B", "type": "restaurant"},
                headers=auth(admin_token)
            )
            assert "outlet" in resp.json()["detail"].lower()
        finally:
            await db.execute(
                "UPDATE core.tenants SET max_outlets = 999 WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_outlet_creation_succeeds_below_limit(
        self, client, admin_token, registered_tenant, db
    ):
        await db.execute(
            "UPDATE core.tenants SET max_outlets = 999 WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        resp = await client.post(
            "/api/v1/outlets",
            json={"name": "Allowed Extra Outlet", "type": "restaurant"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        # Cleanup
        outlet_id = resp.json()["id"]
        await db.execute(
            f'DELETE FROM "{TENANT_SCHEMA}".outlets WHERE id = $1',
            UUID(outlet_id)
        )

    async def test_staff_limit_blocks_creation_when_at_limit(
        self, client, admin_token, registered_tenant, db
    ):
        count = await db.fetchval(
            f'SELECT COUNT(*) FROM "{TENANT_SCHEMA}".user_profiles WHERE is_admin = FALSE'
        )
        await db.execute(
            "UPDATE core.tenants SET max_staff = $1 WHERE schema_name = $2",
            count, TENANT_SCHEMA
        )
        try:
            import uuid
            resp = await client.post(
                "/api/v1/users",
                json={
                    "full_name": "Over Limit Staff",
                    "email": f"overlimit{uuid.uuid4().hex[:4]}@test.com",
                    "phone": "9800000088"
                },
                headers=auth(admin_token)
            )
            assert resp.status_code == 403
        finally:
            await db.execute(
                "UPDATE core.tenants SET max_staff = 999 WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_staff_limit_error_mentions_staff_limit(
        self, client, admin_token, registered_tenant, db
    ):
        count = await db.fetchval(
            f'SELECT COUNT(*) FROM "{TENANT_SCHEMA}".user_profiles WHERE is_admin = FALSE'
        )
        await db.execute(
            "UPDATE core.tenants SET max_staff = $1 WHERE schema_name = $2",
            count, TENANT_SCHEMA
        )
        try:
            import uuid
            resp = await client.post(
                "/api/v1/users",
                json={
                    "full_name": "Over Limit Staff B",
                    "email": f"overlimitb{uuid.uuid4().hex[:4]}@test.com",
                    "phone": "9800000087"
                },
                headers=auth(admin_token)
            )
            assert "staff" in resp.json()["detail"].lower()
        finally:
            await db.execute(
                "UPDATE core.tenants SET max_staff = 999 WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_menu_item_limit_blocks_creation_when_at_limit(
        self, client, admin_token, registered_tenant, db
    ):
        outlet = await db.fetchrow(
            f'SELECT id FROM "{TENANT_SCHEMA}".outlets WHERE is_default = TRUE LIMIT 1'
        )
        count = await db.fetchval(
            f'SELECT COUNT(*) FROM "{TENANT_SCHEMA}".menu_items WHERE outlet_id = $1',
            outlet["id"]
        )
        await db.execute(
            "UPDATE core.tenants SET max_menu_items = $1 WHERE schema_name = $2",
            count, TENANT_SCHEMA
        )
        # Need a category first
        cat = await db.fetchrow(
            f'SELECT id FROM "{TENANT_SCHEMA}".menu_categories LIMIT 1'
        )
        if not cat:
            cat_resp = await client.post(
                "/api/v1/menu/categories",
                json={"name": "Test Cat For Limit"},
                headers=auth(admin_token)
            )
            cat_id = cat_resp.json()["id"]
        else:
            cat_id = str(cat["id"])
        try:
            resp = await client.post(
                "/api/v1/menu/items",
                json={
                    "name": "Over Limit Item",
                    "price": 100,
                    "category_id": cat_id,
                    "item_type": "food"
                },
                headers=auth(admin_token)
            )
            assert resp.status_code == 403
        finally:
            await db.execute(
                "UPDATE core.tenants SET max_menu_items = 9999 WHERE schema_name = $1",
                TENANT_SCHEMA
            )

    async def test_menu_item_limit_error_mentions_menu_item(
        self, client, admin_token, registered_tenant, db
    ):
        outlet = await db.fetchrow(
            f'SELECT id FROM "{TENANT_SCHEMA}".outlets WHERE is_default = TRUE LIMIT 1'
        )
        count = await db.fetchval(
            f'SELECT COUNT(*) FROM "{TENANT_SCHEMA}".menu_items WHERE outlet_id = $1',
            outlet["id"]
        )
        await db.execute(
            "UPDATE core.tenants SET max_menu_items = $1 WHERE schema_name = $2",
            count, TENANT_SCHEMA
        )
        cat = await db.fetchrow(
            f'SELECT id FROM "{TENANT_SCHEMA}".menu_categories LIMIT 1'
        )
        if not cat:
            cat_resp = await client.post(
                "/api/v1/menu/categories",
                json={"name": "Test Cat For Limit B"},
                headers=auth(admin_token)
            )
            cat_id = cat_resp.json()["id"]
        else:
            cat_id = str(cat["id"])
        try:
            resp = await client.post(
                "/api/v1/menu/items",
                json={
                    "name": "Over Limit Item B",
                    "price": 100,
                    "category_id": cat_id,
                    "item_type": "food"
                },
                headers=auth(admin_token)
            )
            assert "menu item" in resp.json()["detail"].lower()
        finally:
            await db.execute(
                "UPDATE core.tenants SET max_menu_items = 9999 WHERE schema_name = $1",
                TENANT_SCHEMA
            )


# SECTION 11 — SECURITY AND BYPASS ATTEMPTS

class TestSubscriptionSecurityAndBypass:

    async def test_manually_crafted_token_cannot_bypass_subscription(
        self, client, registered_tenant, db
    ):
        """
        Forge a JWT with a suspended tenant's schema and try to access features.
        The check happens against the live DB so the DB status wins.
        """
        await _set_status(db, TENANT_SCHEMA, "suspended")
        try:
            # Forge a token that looks like an active tenant using the real schema
            from jose import jwt
            from app.core.config import settings as s
            forged = jwt.encode(
                {
                    "user_id": "00000000-0000-0000-0000-000000000001",
                    "tenant_id": "00000000-0000-0000-0000-000000000002",
                    "schema_name": TENANT_SCHEMA,
                    "is_admin": True,
                    "is_super_admin": False,
                    "type": "access",
                    "exp": 9999999999
                },
                s.JWT_SECRET_KEY,
                algorithm=s.JWT_ALGORITHM
            )
            resp = await client.get(
                "/api/v1/menu/categories",
                headers=auth(forged)
            )
            # Should be 401 (user not found) or 402 (suspended) — never 200
            assert resp.status_code in (401, 402)
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_token_from_another_tenant_cannot_access_other_tenant_subscription(
        self, client, admin_token_b, registered_tenant, registered_tenant_b, db
    ):
        """Tenant B's token must only return tenant B's subscription data."""
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token_b)
        )
        assert resp.status_code == 200
        # The tier returned should reflect tenant B's tier not tenant A's
        tenant_b = await _get_tenant(db, TENANT_SCHEMA_B)
        assert resp.json()["tier"] == tenant_b["subscription_tier"]

    async def test_suspended_tenant_cannot_bypass_by_hitting_auth_me(
        self, client, admin_token, registered_tenant, db
    ):
        """
        /auth/me uses get_current_user (no feature check) so it should work.
        But any feature-gated endpoint should block.
        """
        await _set_status(db, TENANT_SCHEMA, "suspended")
        try:
            me_resp = await client.get(
                "/api/v1/auth/me", headers=auth(admin_token)
            )
            # /auth/me has no require_feature so it should return 200
            assert me_resp.status_code == 200

            feature_resp = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert feature_resp.status_code == 402
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_expired_access_token_rejected_regardless_of_subscription(
        self, client, registered_tenant
    ):
        """An expired JWT is rejected at auth layer before subscription check."""
        from jose import jwt
        from app.core.config import settings as s
        expired = jwt.encode(
            {
                "user_id": "00000000-0000-0000-0000-000000000001",
                "tenant_id": "00000000-0000-0000-0000-000000000002",
                "schema_name": TENANT_SCHEMA,
                "is_admin": True,
                "is_super_admin": False,
                "type": "access",
                "exp": 1  # already expired
            },
            s.JWT_SECRET_KEY,
            algorithm=s.JWT_ALGORITHM
        )
        resp = await client.get(
            "/api/v1/menu/categories", headers=auth(expired)
        )
        assert resp.status_code == 401

    async def test_refresh_token_cannot_be_used_as_access_token(
        self, client, admin_refresh_token, registered_tenant
    ):
        """Using a refresh token where an access token is expected must fail."""
        resp = await client.get(
            "/api/v1/menu/categories", headers=auth(admin_refresh_token)
        )
        assert resp.status_code == 401

    async def test_subscription_check_cannot_be_bypassed_with_wrong_token_type(
        self, client, registered_tenant
    ):
        """Token with wrong type field must be rejected."""
        from jose import jwt
        from app.core.config import settings as s
        wrong_type = jwt.encode(
            {
                "user_id": "00000000-0000-0000-0000-000000000001",
                "schema_name": TENANT_SCHEMA,
                "is_admin": True,
                "type": "refresh",  # wrong type
                "exp": 9999999999
            },
            s.JWT_SECRET_KEY,
            algorithm=s.JWT_ALGORITHM
        )
        resp = await client.get(
            "/api/v1/menu/categories", headers=auth(wrong_type)
        )
        assert resp.status_code == 401

    async def test_subscription_state_changes_take_effect_immediately(
        self, client, admin_token, registered_tenant, db
    ):
        """
        Proves there is no caching — the check hits the DB live on every request.
        Status changes must take effect on the very next request.
        """
        # Step 1: active — allowed
        await _restore(db, TENANT_SCHEMA)
        resp1 = await client.get(
            "/api/v1/menu/categories", headers=auth(admin_token)
        )
        assert resp1.status_code == 200

        # Step 2: suspend immediately — blocked
        await _set_status(db, TENANT_SCHEMA, "suspended")
        resp2 = await client.get(
            "/api/v1/menu/categories", headers=auth(admin_token)
        )
        assert resp2.status_code == 402

        # Step 3: restore immediately — allowed again
        await _restore(db, TENANT_SCHEMA)
        resp3 = await client.get(
            "/api/v1/menu/categories", headers=auth(admin_token)
        )
        assert resp3.status_code == 200

    async def test_plan_tier_in_token_is_not_trusted(
        self, client, registered_tenant, db
    ):
        """
        JWT does not carry tier — tier is always loaded from DB.
        Even if someone forges a token claiming a higher tier, the DB tier wins.
        """
        from jose import jwt
        from app.core.config import settings as s

        # Set DB tier to ez
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'ez' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        # Get a real user ID from DB
        user = await db.fetchrow(
            """
            SELECT u.id FROM core.users u
            JOIN core.tenants t ON t.id = u.tenant_id
            WHERE t.schema_name = $1 AND u.is_admin = TRUE
            LIMIT 1
            """,
            TENANT_SCHEMA
        )
        tenant = await _get_tenant(db, TENANT_SCHEMA)

        # Forge a token — tier is not in JWT payload anyway but test proves
        # that hotel features are blocked regardless
        token = jwt.encode(
            {
                "user_id": str(user["id"]),
                "tenant_id": str(tenant["id"]),
                "schema_name": TENANT_SCHEMA,
                "is_admin": True,
                "is_super_admin": False,
                "type": "access",
                "exp": 9999999999
            },
            s.JWT_SECRET_KEY,
            algorithm=s.JWT_ALGORITHM
        )
        try:
            resp = await client.get(
                "/api/v1/hotel/room-types", headers=auth(token)
            )
            assert resp.status_code == 403
        finally:
            await db.execute(
                "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
                TENANT_SCHEMA
            )


# SECTION 12 — TENANT ISOLATION

class TestSubscriptionTenantIsolation:

    async def test_tenant_b_subscription_endpoint_returns_tenant_b_data(
        self, client, admin_token_b, registered_tenant, registered_tenant_b, db
    ):
        resp = await client.get(
            "/api/v1/subscription", headers=auth(admin_token_b)
        )
        assert resp.status_code == 200
        tenant_b = await _get_tenant(db, TENANT_SCHEMA_B)
        assert resp.json()["tier"] == tenant_b["subscription_tier"]

    async def test_tenant_b_history_does_not_include_tenant_a_events(
        self, client, admin_token_b, registered_tenant, registered_tenant_b, db
    ):
        tenant_a = await _get_tenant(db, TENANT_SCHEMA)
        await db.execute(
            """
            INSERT INTO core.subscription_events
                (tenant_id, event_type, created_by)
            VALUES ($1, 'isolation_test_event', 'test')
            """,
            tenant_a["id"]
        )
        try:
            resp = await client.get(
                "/api/v1/subscription/history", headers=auth(admin_token_b)
            )
            assert resp.status_code == 200
            event_types = [e["event_type"] for e in resp.json()]
            assert "isolation_test_event" not in event_types
        finally:
            await _clear_events(db, TENANT_SCHEMA, "isolation_test_event")

    async def test_tenant_a_suspension_does_not_affect_tenant_b(
        self, client, admin_token, admin_token_b,
        registered_tenant, registered_tenant_b, db
    ):
        await _set_status(db, TENANT_SCHEMA, "suspended")
        try:
            # Tenant A is blocked
            resp_a = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token)
            )
            assert resp_a.status_code == 402

            # Tenant B is unaffected
            resp_b = await client.get(
                "/api/v1/menu/categories", headers=auth(admin_token_b)
            )
            assert resp_b.status_code == 200
        finally:
            await _restore(db, TENANT_SCHEMA)

    async def test_tenant_a_plan_change_does_not_affect_tenant_b(
        self, client, admin_token, admin_token_b,
        registered_tenant, registered_tenant_b, db
    ):
        # Set tenant A to ez (hotel blocked)
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'ez' WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        # Set tenant B to max (hotel allowed)
        await db.execute(
            "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
            TENANT_SCHEMA_B
        )
        try:
            resp_a = await client.get(
                "/api/v1/hotel/room-types", headers=auth(admin_token)
            )
            assert resp_a.status_code == 403

            resp_b = await client.get(
                "/api/v1/hotel/room-types", headers=auth(admin_token_b)
            )
            assert resp_b.status_code == 200
        finally:
            await db.execute(
                "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
                TENANT_SCHEMA
            )
            await db.execute(
                "UPDATE core.tenants SET subscription_tier = 'max' WHERE schema_name = $1",
                TENANT_SCHEMA_B
            )

    async def test_payment_receipts_scoped_to_tenant(
        self, client, admin_token, admin_token_b,
        registered_tenant, registered_tenant_b, db
    ):
        # Tenant A submits a receipt
        await client.post(
            "/api/v1/subscription/payment-receipt",
            data=_receipt_payload(TENANT_SCHEMA, "TXN-ISO-A-001"),
            headers=auth(admin_token)
        )
        # Tenant B should not have any of tenant A's receipts in their DB row
        tenant_a = await _get_tenant(db, TENANT_SCHEMA)
        tenant_b = await _get_tenant(db, TENANT_SCHEMA_B)
        receipts_b = await db.fetch(
            "SELECT * FROM core.payment_receipts WHERE tenant_id = $1",
            tenant_b["id"]
        )
        refs_b = [r["payment_reference"] for r in receipts_b]
        assert "TXN-ISO-A-001" not in refs_b

        # Cleanup
        await db.execute(
            "DELETE FROM core.payment_receipts WHERE tenant_id = $1",
            tenant_a["id"]
        )

    async def test_usage_limits_are_per_tenant(
        self, client, admin_token, admin_token_b,
        registered_tenant, registered_tenant_b, db
    ):
        # Set tenant A limit to 1 (at limit)
        await db.execute(
            "UPDATE core.tenants SET max_outlets = 1 WHERE schema_name = $1",
            TENANT_SCHEMA
        )
        # Set tenant B limit to 999
        await db.execute(
            "UPDATE core.tenants SET max_outlets = 999 WHERE schema_name = $1",
            TENANT_SCHEMA_B
        )
        try:
            # Tenant A is blocked
            resp_a = await client.post(
                "/api/v1/outlets",
                json={"name": "A Blocked Outlet", "type": "restaurant"},
                headers=auth(admin_token)
            )
            assert resp_a.status_code == 403

            # Tenant B is allowed
            resp_b = await client.post(
                "/api/v1/outlets",
                json={"name": "B Allowed Outlet", "type": "restaurant"},
                headers=auth(admin_token_b)
            )
            assert resp_b.status_code == 201

            # Cleanup tenant B's outlet
            outlet_id = resp_b.json()["id"]
            await db.execute(
                f'DELETE FROM "{TENANT_SCHEMA_B}".outlets WHERE id = $1',
                UUID(outlet_id)
            )
        finally:
            await db.execute(
                "UPDATE core.tenants SET max_outlets = 999 WHERE schema_name = $1",
                TENANT_SCHEMA
            )
            await db.execute(
                "UPDATE core.tenants SET max_outlets = 999 WHERE schema_name = $1",
                TENANT_SCHEMA_B
            )