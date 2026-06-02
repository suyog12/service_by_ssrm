import pytest
from unittest.mock import patch
from tests.conftest import auth


class TestForgotPasswordPositive:

    async def test_forgot_password_returns_200(self, client, registered_tenant):
        """Valid email and slug returns 200 with generic message"""
        with patch("app.services.auth_service.send_password_reset_email"):
            resp = await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
        assert resp.status_code == 200
        assert "message" in resp.json()

    async def test_forgot_password_creates_reset_token(self, client, registered_tenant, db):
        """A reset token is stored in the database"""
        with patch("app.services.auth_service.send_password_reset_email"):
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
        row = await db.fetchrow(
            """
            SELECT rt.id FROM core.reset_tokens rt
            JOIN core.users u ON u.id = rt.user_id
            WHERE u.email = $1 AND rt.used = FALSE
            """,
            "testadmin@testhotel.com"
        )
        assert row is not None

    async def test_forgot_password_calls_email(self, client, registered_tenant):
        """Email function is called with correct arguments"""
        with patch("app.services.auth_service.send_password_reset_email") as mock_email:
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
        mock_email.assert_called_once()
        call_kwargs = mock_email.call_args
        assert mock_email.call_args.kwargs["to_email"] == "testadmin@testhotel.com"

    async def test_forgot_password_invalidates_old_tokens(self, client, registered_tenant, db):
        """Requesting reset twice invalidates the first token"""
        with patch("app.services.auth_service.send_password_reset_email"):
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
        rows = await db.fetch(
            """
            SELECT rt.id FROM core.reset_tokens rt
            JOIN core.users u ON u.id = rt.user_id
            WHERE u.email = $1 AND rt.used = FALSE
            """,
            "testadmin@testhotel.com"
        )
        assert len(rows) == 1


class TestForgotPasswordNegative:

    async def test_wrong_email_still_returns_200(self, client, registered_tenant):
        """Non-existent email returns same message to prevent enumeration"""
        resp = await client.post("/api/v1/auth/forgot-password", json={
            "email": "nobody@testhotel.com",
            "tenant_slug": "test-hotel-nepal"
        })
        assert resp.status_code == 200
        assert "message" in resp.json()

    async def test_wrong_slug_still_returns_200(self, client, registered_tenant):
        """Non-existent slug returns same message to prevent enumeration"""
        resp = await client.post("/api/v1/auth/forgot-password", json={
            "email": "testadmin@testhotel.com",
            "tenant_slug": "nonexistent-business"
        })
        assert resp.status_code == 200

    async def test_wrong_email_does_not_create_token(self, client, registered_tenant, db):
        """No token is stored for a non-existent email"""
        initial = await db.fetchval(
            "SELECT COUNT(*) FROM core.reset_tokens"
        )
        await client.post("/api/v1/auth/forgot-password", json={
            "email": "ghost@testhotel.com",
            "tenant_slug": "test-hotel-nepal"
        })
        final = await db.fetchval(
            "SELECT COUNT(*) FROM core.reset_tokens"
        )
        assert final == initial


class TestResetPasswordPositive:

    async def test_reset_password_succeeds(self, client, registered_tenant, db):
        """Valid token allows password reset"""
        with patch("app.services.auth_service.send_password_reset_email"):
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })

        with patch("app.services.auth_service.send_password_reset_email") as mock_email:
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
            raw_token = mock_email.call_args.kwargs["reset_token"]

        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": raw_token,
            "new_password": "NewPass@456"
        })
        assert resp.status_code == 200
        assert "message" in resp.json()

        # Restore password so subsequent tests are not affected
        with patch("app.services.auth_service.send_password_reset_email") as mock_email:
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
            restore_token = mock_email.call_args.kwargs["reset_token"]
        await client.post("/api/v1/auth/reset-password", json={
            "token": restore_token,
            "new_password": "TestPass@123"
        })

    async def test_can_login_with_new_password(self, client, registered_tenant, db):
        """After reset, user can login with new password"""
        with patch("app.services.auth_service.send_password_reset_email") as mock_email:
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
            raw_token = mock_email.call_args.kwargs["reset_token"]

        await client.post("/api/v1/auth/reset-password", json={
            "token": raw_token,
            "new_password": "ResetPass@789"
        })

        login = await client.post("/api/v1/auth/login", json={
            "email": "testadmin@testhotel.com",
            "password": "ResetPass@789",
            "tenant_slug": "test-hotel-nepal"
        })
        assert login.status_code == 200

        # Restore original password for other tests
        with patch("app.services.auth_service.send_password_reset_email") as mock_email:
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
            restore_token = mock_email.call_args[1]["reset_token"]
        await client.post("/api/v1/auth/reset-password", json={
            "token": restore_token,
            "new_password": "TestPass@123"
        })

    async def test_token_marked_used_after_reset(self, client, registered_tenant, db):
        """Token is marked used after successful reset"""
        with patch("app.services.auth_service.send_password_reset_email") as mock_email:
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
            raw_token = mock_email.call_args.kwargs["reset_token"]

        await client.post("/api/v1/auth/reset-password", json={
            "token": raw_token,
            "new_password": "TempReset@999"
        })

        row = await db.fetchrow(
            """
            SELECT rt.used FROM core.reset_tokens rt
            JOIN core.users u ON u.id = rt.user_id
            WHERE u.email = $1
            ORDER BY rt.created_at DESC LIMIT 1
            """,
            "testadmin@testhotel.com"
        )
        assert row["used"] is True

        # Restore password
        with patch("app.services.auth_service.send_password_reset_email") as mock_email:
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
            restore_token = mock_email.call_args[1]["reset_token"]
        await client.post("/api/v1/auth/reset-password", json={
            "token": restore_token,
            "new_password": "TestPass@123"
        })


class TestResetPasswordNegative:

    async def test_invalid_token_rejected(self, client, registered_tenant):
        """Random token returns 400"""
        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": "completelyfaketoken",
            "new_password": "NewPass@456"
        })
        assert resp.status_code == 400

    async def test_used_token_rejected(self, client, registered_tenant):
        """Token cannot be used twice"""
        with patch("app.services.auth_service.send_password_reset_email") as mock_email:
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
            raw_token = mock_email.call_args.kwargs["reset_token"]

        await client.post("/api/v1/auth/reset-password", json={
            "token": raw_token,
            "new_password": "FirstReset@123"
        })

        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": raw_token,
            "new_password": "SecondReset@456"
        })
        assert resp.status_code == 400

        # Restore password
        with patch("app.services.auth_service.send_password_reset_email") as mock_email:
            await client.post("/api/v1/auth/forgot-password", json={
                "email": "testadmin@testhotel.com",
                "tenant_slug": "test-hotel-nepal"
            })
            restore_token = mock_email.call_args[1]["reset_token"]
        await client.post("/api/v1/auth/reset-password", json={
            "token": restore_token,
            "new_password": "TestPass@123"
        })