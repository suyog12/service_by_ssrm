import pytest
from datetime import date
from datetime import datetime, timezone, timedelta
from tests.conftest import auth


class TestExpenseCategoryPositive:

    async def test_create_category(self, client, admin_token):
        resp = await client.post(
            "/api/v1/expenses/categories",
            json={"name": "Food & Beverage", "is_petty": False},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Food & Beverage"
        assert data["is_petty"] is False

    async def test_create_petty_cash_category(self, client, admin_token):
        resp = await client.post(
            "/api/v1/expenses/categories",
            json={"name": "Petty Supplies", "is_petty": True},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["is_petty"] is True

    async def test_list_categories(self, client, admin_token, expense_category):
        resp = await client.get(
            "/api/v1/expenses/categories",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert any(c["id"] == expense_category["id"] for c in resp.json())

    async def test_get_single_category(self, client, admin_token, expense_category):
        resp = await client.get(
            f"/api/v1/expenses/categories/{expense_category['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == expense_category["id"]

    async def test_update_category(self, client, admin_token, expense_category):
        resp = await client.patch(
            f"/api/v1/expenses/categories/{expense_category['id']}",
            json={"name": "Updated Category"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Category"

    async def test_delete_unused_category(self, client, admin_token):
        cat = await client.post(
            "/api/v1/expenses/categories",
            json={"name": "To Delete"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/expenses/categories/{cat.json()['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 204


class TestExpenseCategoryNegative:

    async def test_duplicate_name_rejected(self, client, admin_token, expense_category):
        resp = await client.post(
            "/api/v1/expenses/categories",
            json={"name": expense_category["name"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_empty_name_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/expenses/categories",
            json={"name": ""},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_get_nonexistent_category(self, client, admin_token):
        resp = await client.get(
            "/api/v1/expenses/categories/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_delete_category_with_expenses_rejected(
        self, client, admin_token, expense_log
    ):
        resp = await client.delete(
            f"/api/v1/expenses/categories/{expense_log['category_id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_unauthenticated_rejected(self, client):
        resp = await client.get("/api/v1/expenses/categories")
        assert resp.status_code == 403


class TestExpenseLogPositive:

    async def test_create_expense(self, client, admin_token, expense_category):
        resp = await client.post(
            "/api/v1/expenses",
            json={
                "category_id": expense_category["id"],
                "amount": "500.00",
                "description": "Bought vegetables",
                "expense_date": str(date.today()),
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "Bought vegetables"
        assert float(data["amount"]) == 500.0
        assert data["category_id"] == expense_category["id"]

    async def test_create_petty_cash_expense(self, client, admin_token, expense_category):
        resp = await client.post(
            "/api/v1/expenses",
            json={
                "category_id": expense_category["id"],
                "amount": "50.00",
                "description": "Tea and snacks",
                "expense_date": str(date.today()),
                "is_petty": True,
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["is_petty"] is True

    async def test_list_expenses(self, client, admin_token, expense_log):
        resp = await client.get(
            "/api/v1/expenses",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert any(e["id"] == expense_log["id"] for e in resp.json())

    async def test_list_expenses_has_category_name(self, client, admin_token, expense_log):
        resp = await client.get("/api/v1/expenses", headers=auth(admin_token))
        assert resp.status_code == 200
        entry = next(e for e in resp.json() if e["id"] == expense_log["id"])
        assert "category_name" in entry

    async def test_filter_by_is_petty(self, client, admin_token, expense_category):
        await client.post(
            "/api/v1/expenses",
            json={
                "category_id": expense_category["id"],
                "amount": "25.00",
                "description": "Petty item",
                "expense_date": str(date.today()),
                "is_petty": True,
            },
            headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/expenses?is_petty=true",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert all(e["is_petty"] for e in resp.json())

    async def test_filter_by_category(self, client, admin_token, expense_log):
        resp = await client.get(
            f"/api/v1/expenses?category_id={expense_log['category_id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert all(
            e["category_id"] == expense_log["category_id"]
            for e in resp.json()
        )

    async def test_filter_by_date_range(self, client, admin_token, expense_log):
        today = datetime.now(timezone.utc).date().isoformat()
        resp = await client.get(
            f"/api/v1/expenses?date_from={today}&date_to={today}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_single_expense(self, client, admin_token, expense_log):
        resp = await client.get(
            f"/api/v1/expenses/{expense_log['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == expense_log["id"]

    async def test_delete_expense(self, client, admin_token, expense_category):
        exp = await client.post(
            "/api/v1/expenses",
            json={
                "category_id": expense_category["id"],
                "amount": "100.00",
                "description": "To delete",
                "expense_date": str(date.today()),
            },
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/expenses/{exp.json()['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 204

    async def test_expense_with_receipt_url(self, client, admin_token, expense_category):
        resp = await client.post(
            "/api/v1/expenses",
            json={
                "category_id": expense_category["id"],
                "amount": "750.00",
                "description": "Gas bill",
                "expense_date": str(date.today()),
                "receipt_url": "https://receipts.example.com/gas-bill.jpg",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["receipt_url"] is not None


class TestExpenseLogNegative:

    async def test_nonexistent_category_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/expenses",
            json={
                "category_id": "00000000-0000-0000-0000-000000000000",
                "amount": "100.00",
                "description": "Test",
                "expense_date": str(date.today()),
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_zero_amount_rejected(self, client, admin_token, expense_category):
        resp = await client.post(
            "/api/v1/expenses",
            json={
                "category_id": expense_category["id"],
                "amount": "0",
                "description": "Zero amount",
                "expense_date": str(date.today()),
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_missing_description_rejected(self, client, admin_token, expense_category):
        resp = await client.post(
            "/api/v1/expenses",
            json={
                "category_id": expense_category["id"],
                "amount": "100.00",
                "expense_date": str(date.today()),
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_get_nonexistent_expense(self, client, admin_token):
        resp = await client.get(
            "/api/v1/expenses/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_unauthenticated_rejected(self, client):
        resp = await client.get("/api/v1/expenses")
        assert resp.status_code == 403


class TestCashRegisterPositive:

    async def test_open_cash_register(self, client, admin_token):
        resp = await client.post(
            "/api/v1/cash-register",
            json={"action": "open", "cash_amount": "5000.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["action"] == "open"
        assert float(data["cash_amount"]) == 5000.0
        assert data["discrepancy"] is None

    async def test_close_cash_register(self, client, admin_token):
        await client.post(
            "/api/v1/cash-register",
            json={"action": "open", "cash_amount": "5000.00"},
            headers=auth(admin_token)
        )
        resp = await client.post(
            "/api/v1/cash-register",
            json={"action": "close", "cash_amount": "5200.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["action"] == "close"
        assert data["expected_amount"] is not None
        assert data["discrepancy"] is not None

    async def test_list_cash_register(self, client, admin_token):
        await client.post(
            "/api/v1/cash-register",
            json={"action": "open", "cash_amount": "3000.00"},
            headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/cash-register",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_list_cash_register_by_date(self, client, admin_token):
        await client.post(
            "/api/v1/cash-register",
            json={"action": "open", "cash_amount": "4000.00"},
            headers=auth(admin_token)
        )
        nepal_tz = timezone(timedelta(hours=5, minutes=45))
        today = datetime.now(nepal_tz).date().isoformat()
        resp = await client.get(
            f"/api/v1/cash-register?date_filter={today}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_open_with_notes(self, client, admin_token):
        resp = await client.post(
            "/api/v1/cash-register",
            json={
                "action": "open",
                "cash_amount": "2500.00",
                "notes": "Morning shift opening"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["notes"] == "Morning shift opening"


class TestCashRegisterNegative:

    async def test_cannot_open_twice_same_day(self, client, admin_token):
        await client.post(
            "/api/v1/cash-register",
            json={"action": "open", "cash_amount": "5000.00"},
            headers=auth(admin_token)
        )
        resp = await client.post(
            "/api/v1/cash-register",
            json={"action": "open", "cash_amount": "5000.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_cannot_close_without_open(self, client, admin_token):
        resp = await client.post(
            "/api/v1/cash-register",
            json={"action": "close", "cash_amount": "5000.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_invalid_action_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/cash-register",
            json={"action": "invalid", "cash_amount": "5000.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_unauthenticated_rejected(self, client):
        resp = await client.get("/api/v1/cash-register")
        assert resp.status_code == 403


# Fixtures 

@pytest.fixture
async def expense_category(client, admin_token):
    import uuid
    resp = await client.post(
        "/api/v1/expenses/categories",
        json={"name": f"Test Category {uuid.uuid4().hex[:6]}", "is_petty": False},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def expense_log(client, admin_token, expense_category):
    resp = await client.post(
        "/api/v1/expenses",
        json={
            "category_id": expense_category["id"],
            "amount": "250.00",
            "description": "Test expense",
            "expense_date": str(date.today()),
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()