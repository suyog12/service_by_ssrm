import pytest
from tests.conftest import auth


@pytest.fixture
async def credit_account(client, admin_token):
    resp = await client.post(
        "/api/v1/billing/credit-accounts",
        json={
            "account_type": "corporate",
            "display_name": "Test Corp Nepal",
            "contact_person": "Ram Shrestha",
            "billing_email": "billing@testcorp.com",
            "credit_limit": "50000.00",
            "payment_terms": 30
        },
        headers=auth(admin_token)
    )
    if resp.status_code == 400:
        accounts = await client.get(
            "/api/v1/billing/credit-accounts",
            headers=auth(admin_token)
        )
        return next(a for a in accounts.json() if a["display_name"] == "Test Corp Nepal")
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def order_for_credit(client, admin_token):
    cat = await client.post(
        "/api/v1/menu/categories",
        json={"name": "Credit Test Cat"},
        headers=auth(admin_token)
    )
    if cat.status_code == 400:
        cats = await client.get("/api/v1/menu/categories", headers=auth(admin_token))
        cat_id = next(c["id"] for c in cats.json() if c["name"] == "Credit Test Cat")
    else:
        cat_id = cat.json()["id"]

    item = await client.post(
        "/api/v1/menu/items",
        json={"name": "Credit Test Item", "category_id": cat_id, "price": "500.00"},
        headers=auth(admin_token)
    )
    if item.status_code == 400:
        items = await client.get("/api/v1/menu/items", headers=auth(admin_token))
        item_id = next(i["id"] for i in items.json() if i["name"] == "Credit Test Item")
    else:
        item_id = item.json()["id"]

    order = await client.post(
        "/api/v1/orders",
        json={"order_type": "takeaway"},
        headers=auth(admin_token)
    )
    assert order.status_code == 201
    order_id = order.json()["id"]

    await client.post(
        f"/api/v1/orders/{order_id}/items",
        json={"menu_item_id": item_id, "quantity": 1},
        headers=auth(admin_token)
    )

    return order_id


class TestCreditAccountPositive:

    async def test_create_corporate_account(self, client, admin_token):
        resp = await client.post(
            "/api/v1/billing/credit-accounts",
            json={
                "account_type": "corporate",
                "display_name": "New Corp Ltd",
                "credit_limit": "100000.00",
                "payment_terms": 30
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["account_type"] == "corporate"
        assert float(data["credit_limit"]) == 100000.00
        assert float(data["current_balance"]) == 0.00
        assert data["is_active"] is True

    async def test_create_individual_account(self, client, admin_token):
        resp = await client.post(
            "/api/v1/billing/credit-accounts",
            json={
                "account_type": "individual",
                "display_name": "VIP Customer",
                "credit_limit": "10000.00"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["account_type"] == "individual"

    async def test_list_credit_accounts(self, client, admin_token, credit_account):
        resp = await client.get(
            "/api/v1/billing/credit-accounts",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        names = [a["display_name"] for a in resp.json()]
        assert credit_account["display_name"] in names

    async def test_get_credit_account(self, client, admin_token, credit_account):
        resp = await client.get(
            f"/api/v1/billing/credit-accounts/{credit_account['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == credit_account["id"]

    async def test_update_credit_limit(self, client, admin_token, credit_account):
        resp = await client.patch(
            f"/api/v1/billing/credit-accounts/{credit_account['id']}",
            json={"credit_limit": "75000.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert float(resp.json()["credit_limit"]) == 75000.00

    async def test_post_bill_to_credit_account(
        self, client, admin_token, credit_account, order_for_credit
    ):
        create = await client.post(
            "/api/v1/billing/bills",
            json={
                "order_id": order_for_credit,
                "credit_account_id": credit_account["id"],
                "is_corporate": True,
                "corporate_name": credit_account["display_name"]
            },
            headers=auth(admin_token)
        )
        assert create.status_code == 201
        bill_id = create.json()["id"]
        total = float(create.json()["total_amount"])

        resp = await client.post(
            f"/api/v1/billing/bills/{bill_id}/payment",
            json={"method": "credit_account", "amount": str(total)},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "credit_posted"

        account_resp = await client.get(
            f"/api/v1/billing/credit-accounts/{credit_account['id']}",
            headers=auth(admin_token)
        )
        assert float(account_resp.json()["current_balance"]) > 0

    async def test_settle_credit_account(
        self, client, admin_token, credit_account, order_for_credit, db
    ):
        # Set a known balance directly
        schema = "tenant_test_hotel_nepal"
        await db.execute(
            f'UPDATE "{schema}".credit_accounts SET current_balance = 5000 WHERE id = $1',
            credit_account["id"]
        )

        resp = await client.post(
            f"/api/v1/billing/credit-accounts/{credit_account['id']}/settle",
            json={"amount": "2000.00", "reference": "Bank Transfer #123"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert float(resp.json()["current_balance"]) == 3000.00

    async def test_get_credit_statement_html(
        self, client, admin_token, credit_account
    ):
        resp = await client.get(
            f"/api/v1/billing/credit-accounts/{credit_account['id']}/statement",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert "<!DOCTYPE html>" in resp.text
        assert "CREDIT ACCOUNT STATEMENT" in resp.text


class TestCreditAccountNegative:

    async def test_invalid_account_type_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/billing/credit-accounts",
            json={"account_type": "vip", "display_name": "Test"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_empty_display_name_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/billing/credit-accounts",
            json={"account_type": "corporate", "display_name": ""},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_settlement_exceeds_balance_rejected(
        self, client, admin_token, credit_account, db
    ):
        schema = "tenant_test_hotel_nepal"
        await db.execute(
            f'UPDATE "{schema}".credit_accounts SET current_balance = 100 WHERE id = $1',
            credit_account["id"]
        )
        resp = await client.post(
            f"/api/v1/billing/credit-accounts/{credit_account['id']}/settle",
            json={"amount": "500.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_staff_cannot_create_credit_account(self, client, staff_token):
        resp = await client.post(
            "/api/v1/billing/credit-accounts",
            json={"account_type": "corporate", "display_name": "Test"},
            headers=auth(staff_token)
        )
        assert resp.status_code == 403

    async def test_nonexistent_account_returns_404(self, client, admin_token):
        resp = await client.get(
            "/api/v1/billing/credit-accounts/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404