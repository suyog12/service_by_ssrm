import pytest
from datetime import datetime, timedelta, time
from tests.conftest import auth


class TestOfferCRUDPositive:

    async def test_create_flat_offer(self, client, admin_token):
        resp = await client.post(
            "/api/v1/menu/offers",
            json={
                "name": "Rs 100 Off",
                "offer_type": "flat",
                "discount_value": "100.00",
                "applies_to": "all",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["offer_type"] == "flat"
        assert data["is_active"] is True

    async def test_create_percentage_offer(self, client, admin_token):
        resp = await client.post(
            "/api/v1/menu/offers",
            json={
                "name": "10 Percent Off",
                "offer_type": "percentage",
                "discount_value": "10.00",
                "applies_to": "all",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201

    async def test_create_happy_hour_offer(self, client, admin_token):
        resp = await client.post(
            "/api/v1/menu/offers",
            json={
                "name": "Happy Hour Drinks",
                "offer_type": "happy_hour",
                "discount_value": "20.00",
                "start_time": "16:00:00",
                "end_time": "18:00:00",
                "applies_to": "all",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["start_time"] == "16:00:00"

    async def test_create_category_offer(self, client, admin_token, category):
        resp = await client.post(
            "/api/v1/menu/offers",
            json={
                "name": "Category Deal",
                "offer_type": "percentage",
                "discount_value": "15.00",
                "applies_to": "category",
                "category_id": category["id"],
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["category_id"] == category["id"]

    async def test_list_offers(self, client, admin_token, offer):
        resp = await client.get("/api/v1/menu/offers", headers=auth(admin_token))
        assert resp.status_code == 200
        ids = [o["id"] for o in resp.json()]
        assert offer["id"] in ids

    async def test_get_single_offer(self, client, admin_token, offer):
        resp = await client.get(f"/api/v1/menu/offers/{offer['id']}", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["id"] == offer["id"]

    async def test_update_offer_deactivate(self, client, admin_token, offer):
        resp = await client.patch(
            f"/api/v1/menu/offers/{offer['id']}",
            json={"is_active": False},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_delete_unused_offer(self, client, admin_token):
        create = await client.post(
            "/api/v1/menu/offers",
            json={
                "name": "Deletable Offer",
                "offer_type": "flat",
                "discount_value": "50.00",
                "applies_to": "all",
            },
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/menu/offers/{create.json()['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_eligible_offers_excludes_time_restricted(self, client, admin_token):
        # Happy hour far outside current time should not appear as eligible
        far_future_hour = (datetime.now() + timedelta(hours=10)).time()
        far_future_end = (datetime.now() + timedelta(hours=11)).time()
        await client.post(
            "/api/v1/menu/offers",
            json={
                "name": "Late Night Only",
                "offer_type": "happy_hour",
                "discount_value": "10.00",
                "start_time": far_future_hour.strftime("%H:%M:%S"),
                "end_time": far_future_end.strftime("%H:%M:%S"),
                "applies_to": "all",
            },
            headers=auth(admin_token)
        )
        resp = await client.get("/api/v1/menu/offers/eligible", headers=auth(admin_token))
        assert resp.status_code == 200
        names = [o["name"] for o in resp.json()]
        assert "Late Night Only" not in names


class TestOfferCRUDNegative:

    async def test_invalid_offer_type_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/menu/offers",
            json={"name": "Bad", "offer_type": "bogus", "discount_value": "10.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_percentage_over_100_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/menu/offers",
            json={
                "name": "Too Much",
                "offer_type": "percentage",
                "discount_value": "150.00",
                "applies_to": "all",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_category_applies_to_without_category_id_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/menu/offers",
            json={
                "name": "Missing Category",
                "offer_type": "percentage",
                "discount_value": "10.00",
                "applies_to": "category",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_happy_hour_without_times_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/menu/offers",
            json={
                "name": "No Times",
                "offer_type": "happy_hour",
                "discount_value": "10.00",
                "applies_to": "all",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_offer_not_found(self, client, admin_token):
        resp = await client.get(
            "/api/v1/menu/offers/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_unauthenticated_rejected(self, client):
        resp = await client.get("/api/v1/menu/offers")
        assert resp.status_code == 403


class TestBillOfferApplication:

    async def test_apply_flat_offer_to_bill(self, client, admin_token, bill, flat_offer):
        resp = await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": flat_offer["id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert float(data["discount_amt"]) >= 50.0

    async def test_apply_offer_reduces_total(self, client, admin_token, bill, flat_offer):
        before = await client.get(f"/api/v1/billing/bills/{bill['id']}", headers=auth(admin_token))
        before_total = float(before.json()["total_amount"])

        resp = await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": flat_offer["id"]},
            headers=auth(admin_token)
        )
        after_total = float(resp.json()["total_amount"])
        assert after_total < before_total

    async def test_stack_two_offers(self, client, admin_token, bill, flat_offer, percentage_offer):
        first = await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": flat_offer["id"]},
            headers=auth(admin_token)
        )
        assert first.status_code == 200
        first_discount = float(first.json()["discount_amt"])

        second = await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": percentage_offer["id"]},
            headers=auth(admin_token)
        )
        assert second.status_code == 200
        second_discount = float(second.json()["discount_amt"])

        assert second_discount > first_discount

    async def test_list_offers_on_bill(self, client, admin_token, bill, flat_offer):
        await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": flat_offer["id"]},
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["offer_id"] == flat_offer["id"]

    async def test_remove_offer_restores_total(self, client, admin_token, bill, flat_offer):
        before = await client.get(f"/api/v1/billing/bills/{bill['id']}", headers=auth(admin_token))
        original_total = float(before.json()["total_amount"])

        await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": flat_offer["id"]},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/billing/bills/{bill['id']}/offers/{flat_offer['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert float(resp.json()["total_amount"]) == original_total

    async def test_offer_and_manual_discount_coexist(self, client, admin_token, bill, flat_offer):
        await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": flat_offer["id"]},
            headers=auth(admin_token)
        )
        manual = await client.post(
            f"/api/v1/billing/bills/{bill['id']}/discount",
            json={"discount_level": "bill", "discount_pct": "5.00"},
            headers=auth(admin_token)
        )
        assert manual.status_code == 200
        # discount_amt should reflect BOTH the offer and the manual discount
        offer_only_resp = await client.get(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            headers=auth(admin_token)
        )
        offer_discount = float(offer_only_resp.json()[0]["discount_amt"])
        total_discount = float(manual.json()["discount_amt"])
        assert total_discount > offer_discount


class TestBillOfferNegative:

    async def test_apply_nonexistent_offer(self, client, admin_token, bill):
        resp = await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": "00000000-0000-0000-0000-000000000000"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_apply_inactive_offer_rejected(self, client, admin_token, bill, flat_offer):
        await client.patch(
            f"/api/v1/menu/offers/{flat_offer['id']}",
            json={"is_active": False},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": flat_offer["id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_apply_same_offer_twice_rejected(self, client, admin_token, bill, flat_offer):
        await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": flat_offer["id"]},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": flat_offer["id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_apply_item_specific_offer_without_matching_item(
        self, client, admin_token, bill, second_menu_item
    ):
        offer_resp = await client.post(
            "/api/v1/menu/offers",
            json={
                "name": "Specific Item Deal",
                "offer_type": "item_specific",
                "discount_value": "30.00",
                "applies_to": "item",
                "item_id": second_menu_item["id"],
            },
            headers=auth(admin_token)
        )
        offer_id = offer_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": offer_id},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_remove_offer_not_applied(self, client, admin_token, bill, flat_offer):
        resp = await client.delete(
            f"/api/v1/billing/bills/{bill['id']}/offers/{flat_offer['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_apply_offer_to_nonexistent_bill(self, client, admin_token, flat_offer):
        resp = await client.post(
            "/api/v1/billing/bills/00000000-0000-0000-0000-000000000000/offers",
            json={"offer_id": flat_offer["id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_unauthenticated_cannot_apply(self, client, bill, flat_offer):
        resp = await client.post(
            f"/api/v1/billing/bills/{bill['id']}/offers",
            json={"offer_id": flat_offer["id"]},
        )
        assert resp.status_code == 403


# Fixtures

@pytest.fixture
async def category(client, admin_token):
    resp = await client.post(
        "/api/v1/menu/categories",
        json={"name": "Offer Test Category"},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def offer(client, admin_token):
    resp = await client.post(
        "/api/v1/menu/offers",
        json={
            "name": "Standard Test Offer",
            "offer_type": "flat",
            "discount_value": "50.00",
            "applies_to": "all",
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def flat_offer(client, admin_token):
    resp = await client.post(
        "/api/v1/menu/offers",
        json={
            "name": "Flat 50 Off",
            "offer_type": "flat",
            "discount_value": "50.00",
            "applies_to": "all",
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def percentage_offer(client, admin_token):
    resp = await client.post(
        "/api/v1/menu/offers",
        json={
            "name": "10 Percent Off Stack",
            "offer_type": "percentage",
            "discount_value": "10.00",
            "applies_to": "all",
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def menu_category_for_bill(client, admin_token):
    resp = await client.post(
        "/api/v1/menu/categories",
        json={"name": "Bill Test Category"},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def menu_item_for_bill(client, admin_token, menu_category_for_bill):
    resp = await client.post(
        "/api/v1/menu/items",
        json={
            "name": "Bill Test Item",
            "category_id": menu_category_for_bill["id"],
            "price": "500.00",
            "item_type": "food",
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def second_menu_item(client, admin_token, menu_category_for_bill):
    resp = await client.post(
        "/api/v1/menu/items",
        json={
            "name": "Untouched Item",
            "category_id": menu_category_for_bill["id"],
            "price": "300.00",
            "item_type": "food",
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def bill_table(client, admin_token):
    resp = await client.post(
        "/api/v1/floor/tables",
        json={"table_number": f"OFFER-{__import__('uuid').uuid4().hex[:6]}", "capacity": 4},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def bill(client, admin_token, menu_item_for_bill, bill_table):
    order_resp = await client.post(
        "/api/v1/orders",
        json={"order_type": "dine_in", "table_id": bill_table["id"]},
        headers=auth(admin_token)
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["id"]

    item_resp = await client.post(
        f"/api/v1/orders/{order_id}/items",
        json={"menu_item_id": menu_item_for_bill["id"], "quantity": 2},
        headers=auth(admin_token)
    )
    assert item_resp.status_code == 201

    bill_resp = await client.post(
        "/api/v1/billing/bills",
        json={"order_id": order_id},
        headers=auth(admin_token)
    )
    assert bill_resp.status_code == 201
    return bill_resp.json()