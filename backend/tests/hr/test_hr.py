import pytest
from datetime import date, timedelta
from tests.conftest import auth
from datetime import datetime, timezone, timedelta


class TestHRSettingsPositive:

    async def test_get_default_settings(self, client, admin_token):
        resp = await client.get("/api/v1/hr/settings", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "work_hours_per_day" in data
        assert "scheme" in data
        assert "pf_employee_pct" in data

    async def test_update_work_hours(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/hr/settings",
            json={"work_hours_per_day": "9.0"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert float(resp.json()["work_hours_per_day"]) == 9.0

    async def test_update_scheme_to_ssf(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/hr/settings",
            json={"scheme": "ssf"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["scheme"] == "ssf"

    async def test_update_pf_rates(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/hr/settings",
            json={"pf_employee_pct": "10.0", "pf_employer_pct": "10.0"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert float(resp.json()["pf_employee_pct"]) == 10.0


class TestTaxSlabPositive:

    async def test_create_tax_slab(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hr/tax-slabs",
            json={
                "fiscal_year": "2082-83",
                "basic_exemption": "500000",
                "slabs": [
                    {"min": 0, "max": 500000, "rate": 0.00},
                    {"min": 500001, "max": 700000, "rate": 0.01},
                    {"min": 700001, "max": None, "rate": 0.10},
                ]
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["fiscal_year"] == "2082-83"

    async def test_list_tax_slabs(self, client, admin_token, tax_slab):
        resp = await client.get(
            "/api/v1/hr/tax-slabs", headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_activate_tax_slab(self, client, admin_token, tax_slab):
        resp = await client.post(
            f"/api/v1/hr/tax-slabs/{tax_slab['id']}/activate",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True


class TestTaxSlabNegative:

    async def test_duplicate_fiscal_year_rejected(self, client, admin_token, tax_slab):
        resp = await client.post(
            "/api/v1/hr/tax-slabs",
            json={
                "fiscal_year": tax_slab["fiscal_year"],
                "basic_exemption": "500000",
                "slabs": [{"min": 0, "max": None, "rate": 0.10}]
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 400


class TestShiftPositive:

    async def test_create_shift(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hr/shifts",
            json={"name": "Morning", "start_time": "06:00:00", "end_time": "14:00:00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Morning"

    async def test_list_shifts(self, client, admin_token, shift):
        resp = await client.get("/api/v1/hr/shifts", headers=auth(admin_token))
        assert resp.status_code == 200
        assert any(s["id"] == shift["id"] for s in resp.json())

    async def test_get_single_shift(self, client, admin_token, shift):
        resp = await client.get(
            f"/api/v1/hr/shifts/{shift['id']}", headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == shift["id"]

    async def test_update_shift(self, client, admin_token, shift):
        resp = await client.patch(
            f"/api/v1/hr/shifts/{shift['id']}",
            json={"name": "Updated Shift"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Shift"

    async def test_deactivate_shift(self, client, admin_token, shift):
        resp = await client.patch(
            f"/api/v1/hr/shifts/{shift['id']}",
            json={"is_active": False},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_delete_unused_shift(self, client, admin_token):
        s = await client.post(
            "/api/v1/hr/shifts",
            json={"name": "To Delete", "start_time": "22:00:00", "end_time": "06:00:00"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/hr/shifts/{s.json()['id']}", headers=auth(admin_token)
        )
        assert resp.status_code == 204


class TestShiftNegative:

    async def test_duplicate_shift_name_rejected(self, client, admin_token, shift):
        resp = await client.post(
            "/api/v1/hr/shifts",
            json={"name": shift["name"], "start_time": "06:00:00", "end_time": "14:00:00"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_get_nonexistent_shift(self, client, admin_token):
        resp = await client.get(
            "/api/v1/hr/shifts/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_unauthenticated_rejected(self, client):
        resp = await client.get("/api/v1/hr/shifts")
        assert resp.status_code == 403


class TestAttendancePositive:

    async def test_check_in(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hr/attendance/check-in",
            json={},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["check_in_at"] is not None
        assert data["check_out_at"] is None

    async def test_check_out(self, client, admin_token):
        await client.post(
            "/api/v1/hr/attendance/check-in",
            json={},
            headers=auth(admin_token)
        )
        resp = await client.post(
            "/api/v1/hr/attendance/check-out",
            json={},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["check_out_at"] is not None

    async def test_list_attendance(self, client, admin_token):
        await client.post(
            "/api/v1/hr/attendance/check-in", json={}, headers=auth(admin_token)
        )
        resp = await client.get(
            "/api/v1/hr/attendance", headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_list_attendance_filter_by_date(self, client, admin_token):
        await client.post(
            "/api/v1/hr/attendance/check-in", json={}, headers=auth(admin_token)
        )
        nepal_tz = timezone(timedelta(hours=5, minutes=45))
        today = datetime.now(nepal_tz).date().isoformat()
        resp = await client.get(
            f"/api/v1/hr/attendance?date_from={today}&date_to={today}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_check_in_with_shift(self, client, admin_token, shift):
        resp = await client.post(
            "/api/v1/hr/attendance/check-in",
            json={"shift_id": shift["id"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["shift_id"] == shift["id"]


class TestAttendanceNegative:

    async def test_cannot_check_in_twice(self, client, admin_token):
        await client.post(
            "/api/v1/hr/attendance/check-in", json={}, headers=auth(admin_token)
        )
        resp = await client.post(
            "/api/v1/hr/attendance/check-in", json={}, headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_cannot_check_out_without_check_in(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hr/attendance/check-out", json={}, headers=auth(admin_token)
        )
        assert resp.status_code == 400


class TestLeaveTypePositive:

    async def test_create_leave_type(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hr/leave-types",
            json={"name": "Annual Leave", "days_allowed": 18, "is_paid": True},
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Annual Leave"

    async def test_list_leave_types(self, client, admin_token, leave_type):
        resp = await client.get(
            "/api/v1/hr/leave-types", headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert any(lt["id"] == leave_type["id"] for lt in resp.json())

    async def test_update_leave_type(self, client, admin_token, leave_type):
        resp = await client.patch(
            f"/api/v1/hr/leave-types/{leave_type['id']}",
            json={"days_allowed": 20},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["days_allowed"] == 20

    async def test_delete_unused_leave_type(self, client, admin_token):
        lt = await client.post(
            "/api/v1/hr/leave-types",
            json={"name": "To Delete Leave"},
            headers=auth(admin_token)
        )
        resp = await client.delete(
            f"/api/v1/hr/leave-types/{lt.json()['id']}",
            headers=auth(admin_token)
        )
        assert resp.status_code == 204


class TestLeaveTypeNegative:

    async def test_duplicate_name_rejected(self, client, admin_token, leave_type):
        resp = await client.post(
            "/api/v1/hr/leave-types",
            json={"name": leave_type["name"]},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_get_nonexistent_rejected(self, client, admin_token):
        resp = await client.delete(
            "/api/v1/hr/leave-types/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token)
        )
        assert resp.status_code == 404


class TestLeaveRequestPositive:

    async def test_submit_leave_request(self, client, admin_token, leave_type):
        start = str(date.today() + timedelta(days=7))
        end = str(date.today() + timedelta(days=9))
        resp = await client.post(
            "/api/v1/hr/leave-requests",
            json={
                "leave_type_id": leave_type["id"],
                "start_date": start,
                "end_date": end,
                "reason": "Family trip"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    async def test_list_leave_requests(self, client, admin_token, leave_request):
        resp = await client.get(
            "/api/v1/hr/leave-requests", headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert any(lr["id"] == leave_request["id"] for lr in resp.json())

    async def test_approve_leave_request(self, client, admin_token, leave_request):
        resp = await client.post(
            f"/api/v1/hr/leave-requests/{leave_request['id']}/review",
            json={"status": "approved"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_reject_leave_request(self, client, admin_token, leave_type):
        start = str(date.today() + timedelta(days=14))
        end = str(date.today() + timedelta(days=15))
        req = await client.post(
            "/api/v1/hr/leave-requests",
            json={"leave_type_id": leave_type["id"], "start_date": start, "end_date": end},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/hr/leave-requests/{req.json()['id']}/review",
            json={"status": "rejected"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_cancel_leave_request(self, client, admin_token, leave_type):
        start = str(date.today() + timedelta(days=20))
        end = str(date.today() + timedelta(days=21))
        req = await client.post(
            "/api/v1/hr/leave-requests",
            json={"leave_type_id": leave_type["id"], "start_date": start, "end_date": end},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/hr/leave-requests/{req.json()['id']}/cancel",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    async def test_filter_leave_requests_by_status(self, client, admin_token, leave_request):
        resp = await client.get(
            "/api/v1/hr/leave-requests?status=pending",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert all(lr["status"] == "pending" for lr in resp.json())


class TestLeaveRequestNegative:

    async def test_end_before_start_rejected(self, client, admin_token, leave_type):
        resp = await client.post(
            "/api/v1/hr/leave-requests",
            json={
                "leave_type_id": leave_type["id"],
                "start_date": str(date.today() + timedelta(days=5)),
                "end_date": str(date.today() + timedelta(days=3)),
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_review_nonexistent_request(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hr/leave-requests/00000000-0000-0000-0000-000000000000/review",
            json={"status": "approved"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_cannot_review_already_reviewed(self, client, admin_token, leave_request):
        await client.post(
            f"/api/v1/hr/leave-requests/{leave_request['id']}/review",
            json={"status": "approved"},
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/hr/leave-requests/{leave_request['id']}/review",
            json={"status": "rejected"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 400


class TestPayrollPositive:

    async def test_create_payroll_period(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hr/payroll/periods",
            json={
                "period_name": "Shrawan 2082",
                "start_date": "2025-07-17",
                "end_date": "2025-08-16",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    async def test_list_payroll_periods(self, client, admin_token, payroll_period):
        resp = await client.get(
            "/api/v1/hr/payroll/periods", headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert any(p["id"] == payroll_period["id"] for p in resp.json())

    async def test_process_payroll(self, client, admin_token, payroll_period):
        resp = await client.post(
            f"/api/v1/hr/payroll/periods/{payroll_period['id']}/process",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_list_payroll_entries(self, client, admin_token, processed_payroll):
        resp = await client.get(
            f"/api/v1/hr/payroll/periods/{processed_payroll['id']}/entries",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200

    async def test_approve_payroll(self, client, admin_token, processed_payroll):
        resp = await client.post(
            f"/api/v1/hr/payroll/periods/{processed_payroll['id']}/approve",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_mark_paid(self, client, admin_token, processed_payroll):
        await client.post(
            f"/api/v1/hr/payroll/periods/{processed_payroll['id']}/approve",
            headers=auth(admin_token)
        )
        resp = await client.post(
            f"/api/v1/hr/payroll/periods/{processed_payroll['id']}/mark-paid",
            headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"


class TestPayrollNegative:

    async def test_end_before_start_rejected(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hr/payroll/periods",
            json={
                "period_name": "Bad Period",
                "start_date": "2025-08-16",
                "end_date": "2025-07-17",
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_cannot_process_twice(self, client, admin_token, processed_payroll):
        resp = await client.post(
            f"/api/v1/hr/payroll/periods/{processed_payroll['id']}/process",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400

    async def test_cannot_approve_draft(self, client, admin_token, payroll_period):
        resp = await client.post(
            f"/api/v1/hr/payroll/periods/{payroll_period['id']}/approve",
            headers=auth(admin_token)
        )
        assert resp.status_code == 400


class TestShiftHandoverPositive:

    async def test_create_handover(self, client, admin_token, staff_user):
        resp = await client.post(
            "/api/v1/hr/handovers",
            json={
                "incoming_user_id": staff_user["user_id"],
                "notes": "All good",
                "cash_amount": "5000.00"
            },
            headers=auth(admin_token)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["acknowledged"] is False
        assert float(data["cash_amount"]) == 5000.0

    async def test_list_handovers(self, client, admin_token, handover):
        resp = await client.get(
            "/api/v1/hr/handovers", headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert any(h["id"] == handover["id"] for h in resp.json())

    async def test_acknowledge_handover(self, client, admin_token, staff_token, handover):
        resp = await client.post(
            f"/api/v1/hr/handovers/{handover['id']}/acknowledge",
            headers=auth(staff_token)
        )
        assert resp.status_code == 200
        assert resp.json()["acknowledged"] is True


class TestShiftHandoverNegative:

    async def test_nonexistent_incoming_user(self, client, admin_token):
        resp = await client.post(
            "/api/v1/hr/handovers",
            json={"incoming_user_id": "00000000-0000-0000-0000-000000000000"},
            headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_wrong_user_cannot_acknowledge(self, client, admin_token, handover):
        resp = await client.post(
            f"/api/v1/hr/handovers/{handover['id']}/acknowledge",
            headers=auth(admin_token)
        )
        assert resp.status_code == 403


# Fixtures 

@pytest.fixture
async def tax_slab(client, admin_token):
    import uuid
    fy = f"20{uuid.uuid4().hex[:2]}-{uuid.uuid4().hex[:2]}"
    resp = await client.post(
        "/api/v1/hr/tax-slabs",
        json={
            "fiscal_year": fy,
            "basic_exemption": "500000",
            "slabs": [
                {"min": 0, "max": 500000, "rate": 0.00},
                {"min": 500001, "max": None, "rate": 0.10},
            ]
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def shift(client, admin_token):
    import uuid
    resp = await client.post(
        "/api/v1/hr/shifts",
        json={
            "name": f"Test Shift {uuid.uuid4().hex[:6]}",
            "start_time": "08:00:00",
            "end_time": "16:00:00"
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def leave_type(client, admin_token):
    import uuid
    resp = await client.post(
        "/api/v1/hr/leave-types",
        json={"name": f"Leave {uuid.uuid4().hex[:6]}", "days_allowed": 12, "is_paid": True},
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def leave_request(client, admin_token, leave_type):
    start = str(date.today() + timedelta(days=30))
    end = str(date.today() + timedelta(days=32))
    resp = await client.post(
        "/api/v1/hr/leave-requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": start,
            "end_date": end,
            "reason": "Test leave"
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def payroll_period(client, admin_token):
    resp = await client.post(
        "/api/v1/hr/payroll/periods",
        json={
            "period_name": "Test Period",
            "start_date": "2025-07-17",
            "end_date": "2025-08-16",
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def processed_payroll(client, admin_token, payroll_period):
    await client.post(
        f"/api/v1/hr/payroll/periods/{payroll_period['id']}/process",
        headers=auth(admin_token)
    )
    return payroll_period


@pytest.fixture
async def handover(client, admin_token, staff_user):
    resp = await client.post(
        "/api/v1/hr/handovers",
        json={
            "incoming_user_id": staff_user["user_id"],
            "notes": "Handover notes",
            "cash_amount": "3000.00"
        },
        headers=auth(admin_token)
    )
    assert resp.status_code == 201
    return resp.json()