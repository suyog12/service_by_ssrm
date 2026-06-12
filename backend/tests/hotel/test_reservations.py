import pytest
from datetime import date, timedelta
from tests.conftest import auth


CHECK_IN = str(date.today() + timedelta(days=10))
CHECK_OUT = str(date.today() + timedelta(days=13))


class TestReservationPositive:

    async def test_create_reservation(self, client, admin_token, room, guest):
        resp = await client.post(
            "/api/v1/hotel/reservations",
            json={
                "room_id": room["id"],
                "guest_id": guest["id"],
                "check_in_date": CHECK_IN,
                "check_out_date": CHECK_OUT,
                "adults": 2,
                "rate_per_night": "3500.00",
                "booking_source": "phone",
                "meal_plan": "bed_breakfast"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["total_nights"] == 3
        assert float(data["total_amount"]) == 10500.00

    async def test_reservation_appears_in_list(self, client, admin_token, reservation):
        resp = await client.get(
            "/api/v1/hotel/reservations",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert str(reservation["id"]) in ids

    async def test_get_single_reservation(self, client, admin_token, reservation):
        resp = await client.get(
            f"/api/v1/hotel/reservations/{reservation['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == reservation["id"]

    async def test_update_reservation_notes(self, client, admin_token, reservation):
        resp = await client.patch(
            f"/api/v1/hotel/reservations/{reservation['id']}",
            json={"notes": "Early check-in requested", "meal_plan": "full_board"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Early check-in requested"

    async def test_filter_by_status(self, client, admin_token, reservation):
        resp = await client.get(
            "/api/v1/hotel/reservations?status=confirmed",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert all(r["status"] == "confirmed" for r in resp.json())

    async def test_filter_by_guest(self, client, admin_token, reservation, guest):
        resp = await client.get(
            f"/api/v1/hotel/reservations?guest_id={guest['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_cancel_reservation(self, client, admin_token, room, guest):
        create = await client.post(
            "/api/v1/hotel/reservations",
            json={
                "room_id": room["id"],
                "guest_id": guest["id"],
                "check_in_date": str(date.today() + timedelta(days=20)),
                "check_out_date": str(date.today() + timedelta(days=22)),
                "adults": 1,
                "rate_per_night": "3500.00",
                "booking_source": "whatsapp",
                "meal_plan": "room_only"
            },
            headers=auth(admin_token)
        )
        assert create.status_code == 201
        res_id = create.json()["id"]
        resp = await client.post(
            f"/api/v1/hotel/reservations/{res_id}/cancel",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_check_in(self, client, admin_token, reservation):
        resp = await client.post(
            f"/api/v1/hotel/reservations/{reservation['id']}/check-in",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "checked_in"

    async def test_check_out(self, client, admin_token, reservation):
        await client.post(
            f"/api/v1/hotel/reservations/{reservation['id']}/check-in",
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/hotel/reservations/{reservation['id']}/check-out",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["reservation"]["status"] == "checked_out"

    async def test_get_folio(self, client, admin_token, reservation):
        await client.post(
            f"/api/v1/hotel/reservations/{reservation['id']}/check-in",
            headers=auth(admin_token)
        )
        resp = await client.get(
            f"/api/v1/hotel/reservations/{reservation['id']}/folio",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "total" in data

    async def test_add_folio_charge(self, client, admin_token, reservation):
        await client.post(
            f"/api/v1/hotel/reservations/{reservation['id']}/check-in",
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/hotel/reservations/{reservation['id']}/folio/charges",
            params={
                "charge_type": "restaurant",
                "description": "Dinner at Summit Restaurant",
                "amount": "1200.00"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["charge_type"] == "restaurant"

    async def test_all_booking_sources_accepted(self, client, admin_token, guest):
        for i, source in enumerate(["direct", "email", "travel_agent", "corporate"]):
            rt = await client.post(
                "/api/v1/hotel/room-types",
                json={"name": f"Source Test Type {i}", "base_price": "3000.00", "max_adults": 2},
                headers=auth(admin_token)
            )
            r = await client.post(
                "/api/v1/hotel/rooms",
                json={"room_type_id": rt.json()["id"], "room_number": f"BS{i}"},
                headers=auth(admin_token)
            )
            resp = await client.post(
                "/api/v1/hotel/reservations",
                json={
                    "room_id": r.json()["id"],
                    "guest_id": guest["id"],
                    "check_in_date": str(date.today() + timedelta(days=30 + i)),
                    "check_out_date": str(date.today() + timedelta(days=31 + i)),
                    "adults": 1,
                    "rate_per_night": "3000.00",
                    "booking_source": source,
                    "meal_plan": "room_only"
                },
                headers=auth(admin_token)
            )
            assert resp.status_code == 201, f"Failed for source: {source}"

    async def test_all_meal_plans_accepted(self, client, admin_token, guest):
        for i, plan in enumerate(["room_only", "bed_breakfast", "half_board", "full_board", "all_inclusive"]):
            rt = await client.post(
                "/api/v1/hotel/room-types",
                json={"name": f"Meal Plan Type {i}", "base_price": "3000.00", "max_adults": 2},
                headers=auth(admin_token)
            )
            r = await client.post(
                "/api/v1/hotel/rooms",
                json={"room_type_id": rt.json()["id"], "room_number": f"MP{i}"},
                headers=auth(admin_token)
            )
            resp = await client.post(
                "/api/v1/hotel/reservations",
                json={
                    "room_id": r.json()["id"],
                    "guest_id": guest["id"],
                    "check_in_date": str(date.today() + timedelta(days=40 + i)),
                    "check_out_date": str(date.today() + timedelta(days=41 + i)),
                    "adults": 1,
                    "rate_per_night": "3000.00",
                    "booking_source": "phone",
                    "meal_plan": plan
                },
                headers=auth(admin_token)
            )
            assert resp.status_code == 201, f"Failed for meal plan: {plan}"


class TestReservationNegative:

    async def test_checkout_before_checkin_rejected(self, client, admin_token, room, guest):
        resp = await client.post(
            "/api/v1/hotel/reservations",
            json={
                "room_id": room["id"],
                "guest_id": guest["id"],
                "check_in_date": CHECK_OUT,
                "check_out_date": CHECK_IN,
                "adults": 1,
                "rate_per_night": "3500.00",
                "booking_source": "phone",
                "meal_plan": "room_only"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_double_booking_rejected(self, client, admin_token, room, guest, reservation):
        resp = await client.post(
            "/api/v1/hotel/reservations",
            json={
                "room_id": room["id"],
                "guest_id": guest["id"],
                "check_in_date": CHECK_IN,
                "check_out_date": CHECK_OUT,
                "adults": 1,
                "rate_per_night": "3500.00",
                "booking_source": "phone",
                "meal_plan": "room_only"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_invalid_booking_source_rejected(self, client, admin_token, room, guest):
        resp = await client.post(
            "/api/v1/hotel/reservations",
            json={
                "room_id": room["id"],
                "guest_id": guest["id"],
                "check_in_date": CHECK_IN,
                "check_out_date": CHECK_OUT,
                "adults": 1,
                "rate_per_night": "3500.00",
                "booking_source": "tiktok",
                "meal_plan": "room_only"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_cannot_checkin_twice(self, client, admin_token, reservation):
        await client.post(
            f"/api/v1/hotel/reservations/{reservation['id']}/check-in",
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/hotel/reservations/{reservation['id']}/check-in",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_cannot_checkout_without_checkin(self, client, admin_token, reservation):
        resp = await client.post(
            f"/api/v1/hotel/reservations/{reservation['id']}/check-out",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_cannot_cancel_checked_in(self, client, admin_token, reservation):
        await client.post(
            f"/api/v1/hotel/reservations/{reservation['id']}/check-in",
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/hotel/reservations/{reservation['id']}/cancel",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_nonexistent_room_rejected(self, client, admin_token, guest):
        resp = await client.post(
            "/api/v1/hotel/reservations",
            json={
                "room_id": "00000000-0000-0000-0000-000000000000",
                "guest_id": guest["id"],
                "check_in_date": CHECK_IN,
                "check_out_date": CHECK_OUT,
                "adults": 1,
                "rate_per_night": "3500.00",
                "booking_source": "phone",
                "meal_plan": "room_only"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_unauthenticated_cannot_list(self, client):
        resp = await client.get("/api/v1/hotel/reservations")
        assert resp.status_code == 403


@pytest.fixture
async def room_type(client, admin_token):
    resp = await client.post(
        "/api/v1/hotel/room-types",
        json={"name": "Reservation Test Type", "base_price": "3500.00", "max_adults": 2},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def room(client, admin_token, room_type):
    resp = await client.post(
        "/api/v1/hotel/rooms",
        json={"room_type_id": room_type["id"], "room_number": "301", "floor": "3"},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def guest(client, admin_token):
    resp = await client.post(
        "/api/v1/hotel/guests",
        json={"full_name": "Reservation Test Guest", "phone": "9822222222"},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def reservation(client, admin_token, room, guest):
    resp = await client.post(
        "/api/v1/hotel/reservations",
        json={
            "room_id": room["id"],
            "guest_id": guest["id"],
            "check_in_date": CHECK_IN,
            "check_out_date": CHECK_OUT,
            "adults": 2,
            "rate_per_night": "3500.00",
            "booking_source": "phone",
            "meal_plan": "bed_breakfast"
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()