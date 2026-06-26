from fastapi import APIRouter, Depends, Query
from uuid import UUID
from typing import Optional
from datetime import date

from app.core.dependencies import require_feature
from app.core.database import get_tenant_db
from app.schemas.hr import (
    ShiftCreate, ShiftUpdate,
    HRSettingsUpdate, TaxSlabCreate,
    AttendanceCheckIn, AttendanceCheckOut, AttendanceOverride,
    LeaveTypeCreate, LeaveTypeUpdate,
    LeaveRequestCreate, LeaveReview,
    PayrollPeriodCreate, PayrollEntryUpdate,
    ShiftHandoverCreate,
)
from app.services import hr_service

router = APIRouter(tags=["HR"])


# HR Settings 

@router.get("/hr/settings")
async def get_hr_settings(
    current_user: dict = Depends(require_feature("hr.view_staff", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.get_hr_settings(db, schema)


@router.patch("/hr/settings")
async def update_hr_settings(
    body: HRSettingsUpdate,
    current_user: dict = Depends(require_feature("hr.view_staff", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        return await hr_service.update_hr_settings(db, schema, data)


# Tax Slabs 

@router.post("/hr/tax-slabs", status_code=201)
async def create_tax_slab(
    body: TaxSlabCreate,
    current_user: dict = Depends(require_feature("hr.payroll", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.create_tax_slab(db, schema, body.model_dump())


@router.get("/hr/tax-slabs")
async def list_tax_slabs(
    current_user: dict = Depends(require_feature("hr.payroll", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.list_tax_slabs(db, schema)


@router.post("/hr/tax-slabs/{slab_id}/activate")
async def activate_tax_slab(
    slab_id: UUID,
    current_user: dict = Depends(require_feature("hr.payroll", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.set_active_tax_slab(db, schema, slab_id)


# Shifts 

@router.post("/hr/shifts", status_code=201)
async def create_shift(
    body: ShiftCreate,
    current_user: dict = Depends(require_feature("hr.view_staff", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.create_shift(db, schema, body.model_dump())


@router.get("/hr/shifts")
async def list_shifts(
    current_user: dict = Depends(require_feature("hr.view_staff", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.list_shifts(db, schema)


@router.get("/hr/shifts/{shift_id}")
async def get_shift(
    shift_id: UUID,
    current_user: dict = Depends(require_feature("hr.view_staff", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.get_shift(db, schema, shift_id)


@router.patch("/hr/shifts/{shift_id}")
async def update_shift(
    shift_id: UUID,
    body: ShiftUpdate,
    current_user: dict = Depends(require_feature("hr.view_staff", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        return await hr_service.update_shift(db, schema, shift_id, data)


@router.delete("/hr/shifts/{shift_id}", status_code=204)
async def delete_shift(
    shift_id: UUID,
    current_user: dict = Depends(require_feature("hr.view_staff", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        await hr_service.delete_shift(db, schema, shift_id)


# Attendance 

@router.post("/hr/attendance/check-in", status_code=201)
async def check_in(
    body: AttendanceCheckIn,
    current_user: dict = Depends(require_feature("hr.attendance", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.check_in(
            db, schema, current_user["user_id"], body.model_dump()
        )


@router.post("/hr/attendance/check-out")
async def check_out(
    body: AttendanceCheckOut,
    current_user: dict = Depends(require_feature("hr.attendance", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.check_out(
            db, schema, current_user["user_id"], body.model_dump()
        )


@router.get("/hr/attendance")
async def list_attendance(
    user_id: Optional[UUID] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    current_user: dict = Depends(require_feature("hr.attendance", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.list_attendance(
            db, schema, user_id, date_from, date_to
        )


@router.post("/hr/attendance/override", status_code=201)
async def override_attendance(
    body: AttendanceOverride,
    current_user: dict = Depends(require_feature("hr.attendance", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.admin_override_attendance(
            db, schema, body.model_dump(), current_user["user_id"]
        )


# Leave Types 

@router.post("/hr/leave-types", status_code=201)
async def create_leave_type(
    body: LeaveTypeCreate,
    current_user: dict = Depends(require_feature("hr.leave_approve", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.create_leave_type(db, schema, body.model_dump())


@router.get("/hr/leave-types")
async def list_leave_types(
    current_user: dict = Depends(require_feature("hr.view_staff", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.list_leave_types(db, schema)


@router.patch("/hr/leave-types/{leave_type_id}")
async def update_leave_type(
    leave_type_id: UUID,
    body: LeaveTypeUpdate,
    current_user: dict = Depends(require_feature("hr.leave_approve", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        return await hr_service.update_leave_type(db, schema, leave_type_id, data)


@router.delete("/hr/leave-types/{leave_type_id}", status_code=204)
async def delete_leave_type(
    leave_type_id: UUID,
    current_user: dict = Depends(require_feature("hr.leave_approve", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        await hr_service.delete_leave_type(db, schema, leave_type_id)


# Leave Requests 

@router.post("/hr/leave-requests", status_code=201)
async def create_leave_request(
    body: LeaveRequestCreate,
    current_user: dict = Depends(require_feature("hr.view_staff", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.create_leave_request(
            db, schema, current_user["user_id"], body.model_dump()
        )


@router.get("/hr/leave-requests")
async def list_leave_requests(
    user_id: Optional[UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    current_user: dict = Depends(require_feature("hr.view_staff", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.list_leave_requests(db, schema, user_id, status)


@router.post("/hr/leave-requests/{request_id}/review")
async def review_leave_request(
    request_id: UUID,
    body: LeaveReview,
    current_user: dict = Depends(require_feature("hr.leave_approve", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.review_leave_request(
            db, schema, request_id, current_user["user_id"], body.status
        )


@router.post("/hr/leave-requests/{request_id}/cancel")
async def cancel_leave_request(
    request_id: UUID,
    current_user: dict = Depends(require_feature("hr.view_staff", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.cancel_leave_request(
            db, schema, request_id, current_user["user_id"]
        )


# Payroll 

@router.post("/hr/payroll/periods", status_code=201)
async def create_payroll_period(
    body: PayrollPeriodCreate,
    current_user: dict = Depends(require_feature("hr.payroll", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.create_payroll_period(db, schema, body.model_dump())


@router.get("/hr/payroll/periods")
async def list_payroll_periods(
    current_user: dict = Depends(require_feature("hr.payroll", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.list_payroll_periods(db, schema)


@router.post("/hr/payroll/periods/{period_id}/process")
async def process_payroll(
    period_id: UUID,
    current_user: dict = Depends(require_feature("hr.payroll", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.process_payroll(
            db, schema, period_id, current_user["user_id"]
        )


@router.get("/hr/payroll/periods/{period_id}/entries")
async def list_payroll_entries(
    period_id: UUID,
    current_user: dict = Depends(require_feature("hr.payroll", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.list_payroll_entries(db, schema, period_id)


@router.patch("/hr/payroll/entries/{entry_id}")
async def update_payroll_entry(
    entry_id: UUID,
    body: PayrollEntryUpdate,
    current_user: dict = Depends(require_feature("hr.payroll", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.update_payroll_entry(
            db, schema, entry_id, body.model_dump()
        )


@router.post("/hr/payroll/periods/{period_id}/approve")
async def approve_payroll(
    period_id: UUID,
    current_user: dict = Depends(require_feature("hr.payroll", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.approve_payroll(db, schema, period_id)


@router.post("/hr/payroll/periods/{period_id}/mark-paid")
async def mark_payroll_paid(
    period_id: UUID,
    current_user: dict = Depends(require_feature("hr.payroll", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.mark_payroll_paid(db, schema, period_id)


# Shift Handovers 

@router.post("/hr/handovers", status_code=201)
async def create_handover(
    body: ShiftHandoverCreate,
    current_user: dict = Depends(require_feature("hr.view_staff", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.create_handover(
            db, schema, current_user["user_id"], body.model_dump()
        )


@router.get("/hr/handovers")
async def list_handovers(
    user_id: Optional[UUID] = Query(default=None),
    current_user: dict = Depends(require_feature("hr.view_staff", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.list_handovers(db, schema, user_id)


@router.post("/hr/handovers/{handover_id}/acknowledge")
async def acknowledge_handover(
    handover_id: UUID,
    current_user: dict = Depends(require_feature("orders.view", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await hr_service.acknowledge_handover(
            db, schema, handover_id, current_user["user_id"]
        )