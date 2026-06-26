import pytest
from tests.conftest import auth


class TestLoyaltySettingsPositive:

    async def test_get_default_settings(self, client, admin_token):
        resp = await client.get("/api/v1/loyalty/settings", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "is_enabled" in data
        assert "points_per_amount" in data
        assert "amount_per_point" in data
        assert "min_redemption_pts" in data

    async def test_enable_loyalty(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/loyalty/settings",
            json={"is_enabled": True},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_enabled"] is True

    async def test_configure_earn_rate(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/loyalty/settings",
            json={"points_per_amount": "1.0", "amount_per_point": "0.01"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert float(resp.json()["points_per_amount"]) == 1.0

    async def test_configure_min_redemption(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/loyalty/settings",
            json={"min_redemption_pts": 100},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["min_redemption_pts"] == 100


class TestLoyaltyEnrollmentPositive:

    async def test_enroll_customer(self, client, admin_token, loyalty_customer):
        resp = await client.post(
            f"/api/v1/loyalty/customers/{loyalty_customer['id']}/enroll",
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["customer_id"] == loyalty_customer["id"]
        assert data["points_balance"] == 0
        assert data["lifetime_points"] == 0
        assert data["tier"] == "standard"

    async def test_get_account_after_enroll(self, client, admin_token, enrolled_customer):
        customer_id = enrolled_customer["customer_id"]
        resp = await client.get(
            f"/api/v1/loyalty/customers/{customer_id}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["points_balance"] == 0

    async def test_list_transactions_empty(self, client, admin_token, enrolled_customer):
        customer_id = enrolled_customer["customer_id"]
        resp = await client.get(
            f"/api/v1/loyalty/customers/{customer_id}/transactions",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestLoyaltyEnrollmentNegative:

    async def test_enroll_nonexistent_customer(self, client, admin_token):
        resp = await client.post(
            "/api/v1/loyalty/customers/00000000-0000-0000-0000-000000000000/enroll",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_enroll_same_customer_twice(self, client, admin_token, enrolled_customer):
        customer_id = enrolled_customer["customer_id"]
        resp = await client.post(
            f"/api/v1/loyalty/customers/{customer_id}/enroll",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_get_account_not_enrolled(self, client, admin_token, loyalty_customer):
        resp = await client.get(
            f"/api/v1/loyalty/customers/{loyalty_customer['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_unauthenticated_rejected(self, client):
        resp = await client.get("/api/v1/loyalty/settings")
        assert resp.status_code == 403


class TestLoyaltyEarnPositive:

    async def test_points_earned_on_bill_payment(
        self, client, admin_token, loyalty_bill_setup
    ):
        bill_id = loyalty_bill_setup["bill_id"]
        customer_id = loyalty_bill_setup["customer_id"]

        pay = await client.post(
            f"/api/v1/billing/bills/{bill_id}/payment",
            json={"method": "cash", "amount": "1000.00"},
            headers=auth(admin_token)
        )
        assert pay.status_code == 200

        account = await client.get(
            f"/api/v1/loyalty/customers/{customer_id}",
            headers=auth(admin_token)
        )
        assert account.json()["points_balance"] > 0
        assert account.json()["lifetime_points"] > 0

    async def test_earn_transaction_recorded(
        self, client, admin_token, loyalty_bill_setup
    ):
        bill_id = loyalty_bill_setup["bill_id"]
        customer_id = loyalty_bill_setup["customer_id"]

        await client.post(
            f"/api/v1/billing/bills/{bill_id}/payment",
            json={"method": "cash", "amount": "1000.00"},
            headers=auth(admin_token)
        )

        txns = await client.get(
            f"/api/v1/loyalty/customers/{customer_id}/transactions",
            headers=auth(admin_token)
        )
        assert len(txns.json()) == 1
        assert txns.json()[0]["transaction_type"] == "earn"
        assert txns.json()[0]["points"] > 0

    async def test_no_points_if_loyalty_disabled(
        self, client, admin_token, loyalty_bill_setup
    ):
        # Disable loyalty
        await client.patch(
            "/api/v1/loyalty/settings",
            json={"is_enabled": False},
            headers=auth(admin_token)
        )

        bill_id = loyalty_bill_setup["bill_id"]
        customer_id = loyalty_bill_setup["customer_id"]

        await client.post(
            f"/api/v1/billing/bills/{bill_id}/payment",
            json={"method": "cash", "amount": "1000.00"},
            headers=auth(admin_token)
        )

        account = await client.get(
            f"/api/v1/loyalty/customers/{customer_id}",
            headers=auth(admin_token)
        )
        assert account.json()["points_balance"] == 0

        # Re-enable for other tests
        await client.patch(
            "/api/v1/loyalty/settings",
            json={"is_enabled": True},
            headers=auth(admin_token)
        )


class TestLoyaltyRedeemPositive:

    async def test_redeem_points_reduces_bill_total(
        self, client, admin_token, redeem_setup
    ):
        bill_id = redeem_setup["bill_id"]
        before_total = float(redeem_setup["bill_total"])

        resp = await client.post(
            f"/api/v1/billing/bills/{bill_id}/loyalty/redeem",
            json={"points_to_redeem": 100},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        after_total = float(resp.json()["total_amount"])
        assert after_total < before_total

    async def test_redeem_deducts_from_balance(
        self, client, admin_token, redeem_setup
    ):
        customer_id = redeem_setup["customer_id"]
        before_balance = redeem_setup["initial_balance"]

        await client.post(
            f"/api/v1/billing/bills/{redeem_setup['bill_id']}/loyalty/redeem",
            json={"points_to_redeem": 100},
            headers=auth(admin_token)
        )

        account = await client.get(
            f"/api/v1/loyalty/customers/{customer_id}",
            headers=auth(admin_token)
        )
        assert account.json()["points_balance"] == before_balance - 100

    async def test_void_bill_returns_redeemed_points(
        self, client, admin_token, redeem_setup
    ):
        customer_id = redeem_setup["customer_id"]
        bill_id = redeem_setup["bill_id"]

        await client.post(
            f"/api/v1/billing/bills/{bill_id}/loyalty/redeem",
            json={"points_to_redeem": 100},
            headers=auth(admin_token)
        )
        after_redeem = await client.get(
            f"/api/v1/loyalty/customers/{customer_id}",
            headers=auth(admin_token)
        )
        balance_after_redeem = after_redeem.json()["points_balance"]

        await client.post(
            f"/api/v1/billing/bills/{bill_id}/void",
            params={"reason": "Test void"},
            headers=auth(admin_token)
        )

        after_void = await client.get(
            f"/api/v1/loyalty/customers/{customer_id}",
            headers=auth(admin_token)
        )
        assert after_void.json()["points_balance"] == balance_after_redeem + 100


class TestLoyaltyRedeemNegative:

    async def test_redeem_below_minimum(self, client, admin_token, redeem_setup):
        await client.patch(
            "/api/v1/loyalty/settings",
            json={"min_redemption_pts": 500},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/billing/bills/{redeem_setup['bill_id']}/loyalty/redeem",
            json={"points_to_redeem": 10},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        # Reset
        await client.patch(
            "/api/v1/loyalty/settings",
            json={"min_redemption_pts": 0},
            headers=auth(admin_token)
        )

    async def test_redeem_insufficient_balance(
        self, client, admin_token, redeem_setup
    ):
        resp = await client.post(
            f"/api/v1/billing/bills/{redeem_setup['bill_id']}/loyalty/redeem",
            json={"points_to_redeem": 999999},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_redeem_on_nonexistent_bill(self, client, admin_token):
        resp = await client.post(
            "/api/v1/billing/bills/00000000-0000-0000-0000-000000000000/loyalty/redeem",
            json={"points_to_redeem": 10},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_redeem_when_loyalty_disabled(
        self, client, admin_token, redeem_setup
    ):
        await client.patch(
            "/api/v1/loyalty/settings",
            json={"is_enabled": False},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/billing/bills/{redeem_setup['bill_id']}/loyalty/redeem",
            json={"points_to_redeem": 100},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400
        # Re-enable
        await client.patch(
            "/api/v1/loyalty/settings",
            json={"is_enabled": True},
            headers=auth(admin_token)
        )


# Fixtures

@pytest.fixture
async def loyalty_customer(client, admin_token):
    import uuid
    resp = await client.post(
        "/api/v1/auth/register",
        json={} # customer created via table reservation phone linking
    ) if False else None
    # Create via table reservation which auto-creates customer
    suffix = uuid.uuid4().hex[:8]
    table = await client.post(
        "/api/v1/floor/tables",
        json={"table_number": f"LOY-{suffix}", "capacity": 4},
        headers=auth(admin_token)
    )
    from datetime import datetime, timedelta
    start = (datetime.utcnow() + timedelta(hours=2)).isoformat()
    end = (datetime.utcnow() + timedelta(hours=3)).isoformat()
    res = await client.post(
        "/api/v1/floor/reservations",
        json={
            "customer_name": f"Loyal Customer {suffix}",
            "customer_phone": f"98{suffix[:8]}",
            "party_size": 2,
            "reserved_at": start,
            "reserved_until": end,
        },
        headers=auth(admin_token)
    )
    assert res.status_code == 201
    customer_id = res.json()["customer_id"]
    return {"id": customer_id}


@pytest.fixture
async def enrolled_customer(client, admin_token, loyalty_customer):
    resp = await client.post(
        f"/api/v1/loyalty/customers/{loyalty_customer['id']}/enroll",
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def loyalty_enabled(client, admin_token):
    await client.patch(
        "/api/v1/loyalty/settings",
        json={
            "is_enabled": True,
            "points_per_amount": "1.0",
            "amount_per_point": "0.01",
            "min_redemption_pts": 0,
        },
        headers=auth(admin_token)
    )


@pytest.fixture
async def loyalty_bill_setup(client, admin_token, loyalty_enabled):
    import uuid
    suffix = uuid.uuid4().hex[:8]

    # Create customer via reservation
    table = await client.post(
        "/api/v1/floor/tables",
        json={"table_number": f"LOY-B-{suffix}", "capacity": 4},
        headers=auth(admin_token)
    )
    from datetime import datetime, timedelta
    start = (datetime.utcnow() + timedelta(hours=10)).isoformat()
    end = (datetime.utcnow() + timedelta(hours=11)).isoformat()
    res = await client.post(
        "/api/v1/floor/reservations",
        json={
            "customer_name": f"Bill Customer {suffix}",
            "customer_phone": f"97{suffix[:8]}",
            "party_size": 2,
            "reserved_at": start,
            "reserved_until": end,
        },
        headers=auth(admin_token)
    )
    customer_id = res.json()["customer_id"]

    # Enroll
    await client.post(
        f"/api/v1/loyalty/customers/{customer_id}/enroll",
        headers=auth(admin_token)
    )

    # Create category, item, order, bill
    cat = await client.post(
        "/api/v1/menu/categories",
        json={"name": f"Loy Cat {suffix}"},
        headers=auth(admin_token)
    )
    item = await client.post(
        "/api/v1/menu/items",
        json={"name": f"Loy Item {suffix}", "category_id": cat.json()["id"], "price": "1000.00", "item_type": "food"},
        headers=auth(admin_token)
    )
    order_table = await client.post(
        "/api/v1/floor/tables",
        json={"table_number": f"LOY-O-{suffix}", "capacity": 4},
        headers=auth(admin_token)
    )
    order = await client.post(
        "/api/v1/orders",
        json={"order_type": "dine_in", "table_id": order_table.json()["id"], "customer_id": customer_id},
        headers=auth(admin_token)
    )
    await client.post(
        f"/api/v1/orders/{order.json()['id']}/items",
        json={"menu_item_id": item.json()["id"], "quantity": 1},
        headers=auth(admin_token)
    )
    bill = await client.post(
        "/api/v1/billing/bills",
        json={"order_id": order.json()["id"], "customer_id": customer_id},
        headers=auth(admin_token)
    )
    assert bill.status_code == 201
    return {"bill_id": bill.json()["id"], "customer_id": customer_id}


@pytest.fixture
async def redeem_setup(client, admin_token, loyalty_enabled):
    """Creates a customer with 1000 points already earned, and an open bill."""
    import uuid
    suffix = uuid.uuid4().hex[:8]

    table = await client.post(
        "/api/v1/floor/tables",
        json={"table_number": f"LOY-R-{suffix}", "capacity": 4},
        headers=auth(admin_token)
    )
    from datetime import datetime, timedelta
    start = (datetime.utcnow() + timedelta(hours=12)).isoformat()
    end = (datetime.utcnow() + timedelta(hours=13)).isoformat()
    res = await client.post(
        "/api/v1/floor/reservations",
        json={
            "customer_name": f"Redeem Customer {suffix}",
            "customer_phone": f"96{suffix[:8]}",
            "party_size": 2,
            "reserved_at": start,
            "reserved_until": end,
        },
        headers=auth(admin_token)
    )
    customer_id = res.json()["customer_id"]
    await client.post(
        f"/api/v1/loyalty/customers/{customer_id}/enroll",
        headers=auth(admin_token)
    )

    # Earn points via a first paid bill
    cat = await client.post(
        "/api/v1/menu/categories",
        json={"name": f"Redeem Cat {suffix}"},
        headers=auth(admin_token)
    )
    item = await client.post(
        "/api/v1/menu/items",
        json={"name": f"Redeem Item {suffix}", "category_id": cat.json()["id"], "price": "1000.00", "item_type": "food"},
        headers=auth(admin_token)
    )
    order_table_1 = await client.post(
        "/api/v1/floor/tables",
        json={"table_number": f"LOY-R1-{suffix}", "capacity": 4},
        headers=auth(admin_token)
    )
    order1 = await client.post(
        "/api/v1/orders",
        json={"order_type": "dine_in", "table_id": order_table_1.json()["id"], "customer_id": customer_id},
        headers=auth(admin_token)
    )
    await client.post(
        f"/api/v1/orders/{order1.json()['id']}/items",
        json={"menu_item_id": item.json()["id"], "quantity": 1},
        headers=auth(admin_token)
    )
    bill1 = await client.post(
        "/api/v1/billing/bills",
        json={"order_id": order1.json()["id"], "customer_id": customer_id},
        headers=auth(admin_token)
    )
    await client.post(
        f"/api/v1/billing/bills/{bill1.json()['id']}/payment",
        json={"method": "cash", "amount": "1000.00"},
        headers=auth(admin_token)
    )

    # Get earned balance
    acct = await client.get(
        f"/api/v1/loyalty/customers/{customer_id}",
        headers=auth(admin_token)
    )
    initial_balance = acct.json()["points_balance"]

    # Create a second open bill to redeem against
    order_table_2 = await client.post(
        "/api/v1/floor/tables",
        json={"table_number": f"LOY-R2-{suffix}", "capacity": 4},
        headers=auth(admin_token)
    )
    order2 = await client.post(
        "/api/v1/orders",
        json={"order_type": "dine_in", "table_id": order_table_2.json()["id"], "customer_id": customer_id},
        headers=auth(admin_token)
    )
    await client.post(
        f"/api/v1/orders/{order2.json()['id']}/items",
        json={"menu_item_id": item.json()["id"], "quantity": 1},
        headers=auth(admin_token)
    )
    bill2 = await client.post(
        "/api/v1/billing/bills",
        json={"order_id": order2.json()["id"], "customer_id": customer_id},
        headers=auth(admin_token)
    )
    assert bill2.status_code == 201
    return {
        "bill_id": bill2.json()["id"],
        "bill_total": bill2.json()["total_amount"],
        "customer_id": customer_id,
        "initial_balance": initial_balance,
    }