import pytest
from tests.conftest import auth


@pytest.fixture
async def billed_order(client, admin_token):
    cat = await client.post(
        "/api/v1/menu/categories",
        json={"name": "Billing Test Cat"},
        headers=auth(admin_token)
    )
    if cat.status_code == 400:
        cats = await client.get("/api/v1/menu/categories", headers=auth(admin_token))
        cat_id = next(c["id"] for c in cats.json() if c["name"] == "Billing Test Cat")
    else:
        cat_id = cat.json()["id"]

    item = await client.post(
        "/api/v1/menu/items",
        json={"name": "Bill Test Burger", "category_id": cat_id,
              "price": "350.00", "item_type": "food"},
        headers=auth(admin_token)
    )
    if item.status_code == 400:
        items = await client.get("/api/v1/menu/items", headers=auth(admin_token))
        item_id = next(i["id"] for i in items.json() if i["name"] == "Bill Test Burger")
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
        json={"menu_item_id": item_id, "quantity": 2},
        headers=auth(admin_token)
    )

    return {"order_id": order_id, "item_id": item_id, "item_price": 350.00}


class TestBillPositive:

    async def test_generate_bill(self, client, admin_token, billed_order):
        resp = await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["order_id"] == billed_order["order_id"]
        assert data["status"] == "open"
        assert data["bill_number"].startswith("BILL-")
        assert float(data["subtotal"]) == 700.00
        assert len(data["items"]) == 1

    async def test_bill_applies_vat(self, client, admin_token, billed_order):
        await client.patch(
            "/api/v1/billing/settings",
            json={"vat_mode": "exclusive", "vat_pct": "13.00", "service_charge_pct": "0"},
            headers=auth(admin_token)
        )
        resp = await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert float(resp.json()["vat_amt"]) == 0.00
        assert float(resp.json()["total_amount"]) == 700.00

    async def test_get_bill(self, client, admin_token, billed_order):
        create = await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        bill_id = create.json()["id"]
        resp = await client.get(
            f"/api/v1/billing/bills/{bill_id}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == bill_id

    async def test_list_bills(self, client, admin_token, billed_order):
        await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/billing/bills",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_apply_bill_level_discount(self, client, admin_token, billed_order):
        create = await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        bill_id = create.json()["id"]
        original_total = float(create.json()["total_amount"])

        resp = await client.post(
            f"/api/v1/billing/bills/{bill_id}/discount",
            json={"discount_level": "bill", "discount_pct": "10.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert float(resp.json()["discount_amt"]) == 70.00
        assert float(resp.json()["total_amount"]) < original_total

    async def test_process_cash_payment(self, client, admin_token, billed_order):
        create = await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        bill_id = create.json()["id"]
        total = float(create.json()["total_amount"])

        resp = await client.post(
            f"/api/v1/billing/bills/{bill_id}/payment",
            json={"method": "cash", "amount": str(total)},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"

    async def test_paid_bill_marks_order_billed(self, client, admin_token, billed_order):
        create = await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        bill_id = create.json()["id"]
        total = float(create.json()["total_amount"])

        await client.post(
            f"/api/v1/billing/bills/{bill_id}/payment",
            json={"method": "cash", "amount": str(total)},
            headers=auth(admin_token)
        )

        order_resp = await client.get(
            f"/api/v1/orders/{billed_order['order_id']}",
            headers=auth(admin_token)
        )
        assert order_resp.json()["status"] == "billed"

    async def test_partial_payment(self, client, admin_token, billed_order):
        create = await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        bill_id = create.json()["id"]

        resp = await client.post(
            f"/api/v1/billing/bills/{bill_id}/payment",
            json={"method": "cash", "amount": "200.00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "partial"

    async def test_void_bill(self, client, admin_token, billed_order):
        create = await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        bill_id = create.json()["id"]

        resp = await client.post(
            f"/api/v1/billing/bills/{bill_id}/void?reason=Test+void",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "voided"

    async def test_get_bill_html(self, client, admin_token, billed_order):
        create = await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        bill_id = create.json()["id"]

        resp = await client.get(
            f"/api/v1/billing/bills/{bill_id}/html",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert "<!DOCTYPE html>" in resp.text
        assert "INVOICE" in resp.text
        assert "BILL-" in resp.text


class TestBillNegative:

    async def test_cannot_bill_nonexistent_order(self, client, admin_token):
        resp = await client.post(
            "/api/v1/billing/bills",
            json={"order_id": "00000000-0000-0000-0000-000000000000"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_cannot_bill_same_order_twice(self, client, admin_token, billed_order):
        await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        resp = await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_cannot_void_paid_bill(self, client, admin_token, billed_order):
        create = await client.post(
            "/api/v1/billing/bills",
            json={"order_id": billed_order["order_id"]},
            headers=auth(admin_token)
        )
        bill_id = create.json()["id"]
        total = float(create.json()["total_amount"])

        await client.post(
            f"/api/v1/billing/bills/{bill_id}/payment",
            json={"method": "cash", "amount": str(total)},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/billing/bills/{bill_id}/void?reason=Test",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_unauthenticated_cannot_list_bills(self, client):
        resp = await client.get("/api/v1/billing/bills")
        assert resp.status_code == 403