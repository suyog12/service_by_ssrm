import pytest
import uuid
from datetime import datetime, timedelta
from tests.conftest import auth


def iso(dt: datetime) -> str:
    return dt.isoformat()


class TestReservationPositive:

    async def test_create_reservation_fits_single_table(
        self, client, admin_token, table_small
    ):
        start = datetime.utcnow() + timedelta(hours=2)
        end = start + timedelta(hours=1, minutes=30)
        resp = await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "Ramesh Shrestha",
                "customer_phone": "9811111111",
                "party_size": 2,
                "reserved_at": iso(start),
                "reserved_until": iso(end),
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["table_id"] == table_small["id"]
        assert data["merged_table_ids"] == []
        assert data["party_size"] == 2

    async def test_create_reservation_sets_table_reserved(
        self, client, admin_token, table_small
    ):
        start = datetime.utcnow() + timedelta(hours=3)
        end = start + timedelta(hours=1)
        await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "Sita Lama",
                "customer_phone": "9822222222",
                "party_size": 2,
                "reserved_at": iso(start),
                "reserved_until": iso(end),
            },
            headers=auth(admin_token)
        )
        table_resp = await client.get(
            f"/api/v1/floor/tables/{table_small['id']}",
            headers=auth(admin_token)
        )
        assert table_resp.json()["status"] == "reserved"

    async def test_create_reservation_auto_links_existing_customer(
        self, client, admin_token, table_small
    ):
        start = datetime.utcnow() + timedelta(hours=4)
        end = start + timedelta(hours=1)
        first = await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "Hari Gurung",
                "customer_phone": "9833333333",
                "party_size": 1,
                "reserved_at": iso(start),
                "reserved_until": iso(end),
            },
            headers=auth(admin_token)
        )
        cust_id_1 = first.json()["customer_id"]

        start2 = start + timedelta(days=1)
        end2 = start2 + timedelta(hours=1)
        second = await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "Hari Gurung",
                "customer_phone": "9833333333",
                "party_size": 1,
                "reserved_at": iso(start2),
                "reserved_until": iso(end2),
            },
            headers=auth(admin_token)
        )
        assert second.json()["customer_id"] == cust_id_1

    async def test_create_reservation_merges_tables_for_large_party(
        self, client, admin_token, two_small_tables
    ):
        start = datetime.utcnow() + timedelta(hours=5)
        end = start + timedelta(hours=2)
        resp = await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "Big Group",
                "customer_phone": "9844444444",
                "party_size": 8,
                "reserved_at": iso(start),
                "reserved_until": iso(end),
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["merged_table_ids"]) >= 1

        for t in two_small_tables:
            table_resp = await client.get(
                f"/api/v1/floor/tables/{t['id']}",
                headers=auth(admin_token)
            )
            assert table_resp.json()["status"] == "reserved"

    async def test_list_reservations(self, client, admin_token, reservation):
        resp = await client.get(
            "/api/v1/floor/reservations",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert reservation["id"] in ids

    async def test_filter_by_status(self, client, admin_token, reservation):
        resp = await client.get(
            "/api/v1/floor/reservations?status=confirmed",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert all(r["status"] == "confirmed" for r in resp.json())

    async def test_get_single_reservation(self, client, admin_token, reservation):
        resp = await client.get(
            f"/api/v1/floor/reservations/{reservation['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == reservation["id"]

    async def test_update_party_size(self, client, admin_token, reservation):
        resp = await client.patch(
            f"/api/v1/floor/reservations/{reservation['id']}",
            json={"party_size": 3, "notes": "Window seat please"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Window seat please"

    async def test_seat_reservation_sets_table_occupied(
        self, client, admin_token, reservation, table_small
    ):
        resp = await client.post(
            f"/api/v1/floor/reservations/{reservation['id']}/seat",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        table_resp = await client.get(
            f"/api/v1/floor/tables/{table_small['id']}",
            headers=auth(admin_token)
        )
        assert table_resp.json()["status"] == "occupied"

    async def test_cancel_reservation_releases_table(
        self, client, admin_token, reservation, table_small
    ):
        resp = await client.patch(
            f"/api/v1/floor/reservations/{reservation['id']}",
            json={"status": "cancelled"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        table_resp = await client.get(
            f"/api/v1/floor/tables/{table_small['id']}",
            headers=auth(admin_token)
        )
        assert table_resp.json()["status"] == "available"

    async def test_cancel_merged_reservation_releases_all_tables(
        self, client, admin_token, two_small_tables
    ):
        start = datetime.utcnow() + timedelta(hours=6)
        end = start + timedelta(hours=1)
        create = await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "Group X",
                "customer_phone": "9855555555",
                "party_size": 8,
                "reserved_at": iso(start),
                "reserved_until": iso(end),
            },
            headers=auth(admin_token)
        )
        res_id = create.json()["id"]

        await client.patch(
            f"/api/v1/floor/reservations/{res_id}",
            json={"status": "no_show"},
            headers=auth(admin_token)
        )

        for t in two_small_tables:
            table_resp = await client.get(
                f"/api/v1/floor/tables/{t['id']}",
                headers=auth(admin_token)
            )
            assert table_resp.json()["status"] == "available"

    async def test_subsequent_reservation_can_reuse_released_table(
        self, client, admin_token, table_small
    ):
        start = datetime.utcnow() + timedelta(hours=7)
        end = start + timedelta(hours=1)
        first = await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "First Booking",
                "customer_phone": "9866666666",
                "party_size": 2,
                "reserved_at": iso(start),
                "reserved_until": iso(end),
            },
            headers=auth(admin_token)
        )
        await client.patch(
            f"/api/v1/floor/reservations/{first.json()['id']}",
            json={"status": "cancelled"},
            headers=auth(admin_token)
        )

        second = await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "Second Booking",
                "customer_phone": "9877777777",
                "party_size": 2,
                "reserved_at": iso(start),
                "reserved_until": iso(end),
            },
            headers=auth(admin_token)
        )
        assert second.status_code == 201
        assert second.json()["table_id"] == table_small["id"]


class TestReservationNegative:

    async def test_reserved_until_before_reserved_at_rejected(
        self, client, admin_token, table_small
    ):
        start = datetime.utcnow() + timedelta(hours=2)
        end = start - timedelta(minutes=30)
        resp = await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "Bad Time",
                "customer_phone": "9888888888",
                "party_size": 2,
                "reserved_at": iso(start),
                "reserved_until": iso(end),
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_party_size_zero_rejected(self, client, admin_token, table_small):
        start = datetime.utcnow() + timedelta(hours=2)
        end = start + timedelta(hours=1)
        resp = await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "Zero Party",
                "customer_phone": "9899999999",
                "party_size": 0,
                "reserved_at": iso(start),
                "reserved_until": iso(end),
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_no_availability_for_overlapping_window(
        self, client, admin_token, table_small
    ):
        start = datetime.utcnow() + timedelta(hours=8)
        end = start + timedelta(hours=1)
        await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "Booked First",
                "customer_phone": "9800000001",
                "party_size": 2,
                "reserved_at": iso(start),
                "reserved_until": iso(end),
            },
            headers=auth(admin_token)
        )
        overlap_start = start + timedelta(minutes=30)
        overlap_end = overlap_start + timedelta(hours=1)
        resp = await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "Booked Second",
                "customer_phone": "9800000002",
                "party_size": 2,
                "reserved_at": iso(overlap_start),
                "reserved_until": iso(overlap_end),
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_party_too_large_for_any_combination(
        self, client, admin_token, table_small
    ):
        start = datetime.utcnow() + timedelta(hours=9)
        end = start + timedelta(hours=1)
        resp = await client.post(
            "/api/v1/floor/reservations",
            json={
                "customer_name": "Huge Party",
                "customer_phone": "9800000003",
                "party_size": 500,
                "reserved_at": iso(start),
                "reserved_until": iso(end),
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_reservation_not_found(self, client, admin_token):
        resp = await client.get(
            "/api/v1/floor/reservations/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_seat_non_confirmed_reservation_fails(
        self, client, admin_token, reservation
    ):
        await client.patch(
            f"/api/v1/floor/reservations/{reservation['id']}",
            json={"status": "cancelled"},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/floor/reservations/{reservation['id']}/seat",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_unauthenticated_rejected(self, client):
        resp = await client.get("/api/v1/floor/reservations")
        assert resp.status_code == 403


# Fixtures

@pytest.fixture
async def table_small(client, admin_token):
    suffix = uuid.uuid4().hex[:8]
    resp = await client.post(
        "/api/v1/floor/tables",
        json={"table_number": f"RES-{suffix}", "capacity": 4},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def two_small_tables(client, admin_token):
    suffix = uuid.uuid4().hex[:8]
    t1 = await client.post(
        "/api/v1/floor/tables",
        json={"table_number": f"RES-{suffix}-A", "capacity": 4},
        headers=auth(admin_token)
    )
    t2 = await client.post(
        "/api/v1/floor/tables",
        json={"table_number": f"RES-{suffix}-B", "capacity": 4},
        headers=auth(admin_token)
    )
    assert t1.status_code == 201
    assert t2.status_code == 201
    return [t1.json(), t2.json()]


@pytest.fixture
async def reservation(client, admin_token, table_small):
    start = datetime.utcnow() + timedelta(hours=1)
    end = start + timedelta(hours=1)
    resp = await client.post(
        "/api/v1/floor/reservations",
        json={
            "customer_name": "Fixture Customer",
            "customer_phone": "9800099000",
            "party_size": 2,
            "reserved_at": iso(start),
            "reserved_until": iso(end),
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()