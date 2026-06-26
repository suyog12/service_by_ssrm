from fastapi import APIRouter, Depends, Query
from uuid import UUID
from typing import Optional
from datetime import date

from app.core.dependencies import require_feature
from app.core.database import get_tenant_db
from app.schemas.expenses import (
    ExpenseCategoryCreate, ExpenseCategoryUpdate,
    ExpenseLogCreate, CashRegisterAction
)
from app.services import expenses_service

router = APIRouter(tags=["Expenses"])


# Expense Categories 

@router.post("/expenses/categories", status_code=201)
async def create_category(
    body: ExpenseCategoryCreate,
    current_user: dict = Depends(require_feature("expenses.view", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await expenses_service.create_category(db, schema, body.model_dump())


@router.get("/expenses/categories")
async def list_categories(
    current_user: dict = Depends(require_feature("expenses.view", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await expenses_service.list_categories(db, schema)


@router.get("/expenses/categories/{category_id}")
async def get_category(
    category_id: UUID,
    current_user: dict = Depends(require_feature("expenses.view", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await expenses_service.get_category(db, schema, category_id)


@router.patch("/expenses/categories/{category_id}")
async def update_category(
    category_id: UUID,
    body: ExpenseCategoryUpdate,
    current_user: dict = Depends(require_feature("expenses.view", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        return await expenses_service.update_category(db, schema, category_id, data)


@router.delete("/expenses/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: UUID,
    current_user: dict = Depends(require_feature("expenses.view", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        await expenses_service.delete_category(db, schema, category_id)


# Expense Logs 

@router.post("/expenses", status_code=201)
async def create_expense(
    body: ExpenseLogCreate,
    current_user: dict = Depends(require_feature("expenses.log", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await expenses_service.create_expense(
            db, schema, body.model_dump(), current_user["user_id"]
        )


@router.get("/expenses")
async def list_expenses(
    outlet_id: Optional[UUID] = Query(default=None),
    category_id: Optional[UUID] = Query(default=None),
    is_petty: Optional[bool] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    current_user: dict = Depends(require_feature("expenses.view", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await expenses_service.list_expenses(
            db, schema, outlet_id, category_id, is_petty, date_from, date_to
        )


@router.get("/expenses/{expense_id}")
async def get_expense(
    expense_id: UUID,
    current_user: dict = Depends(require_feature("expenses.view", "view")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        return await expenses_service.get_expense(db, schema, expense_id)


@router.delete("/expenses/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: UUID,
    current_user: dict = Depends(require_feature("expenses.view", "edit")),
):
    schema = current_user["schema_name"]
    async for db in get_tenant_db(schema):
        await expenses_service.delete_expense(db, schema, expense_id)


# Cash Register 

@router.post("/cash-register", status_code=201)
async def cash_register_action(
    body: CashRegisterAction,
    current_user: dict = Depends(require_feature("cash.open_close", "edit")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await expenses_service.cash_register_action(
            db, schema, outlet_id, body.model_dump(), current_user["user_id"]
        )


@router.get("/cash-register")
async def list_cash_register(
    date_filter: Optional[date] = Query(default=None),
    current_user: dict = Depends(require_feature("cash.view_drawer", "view")),
):
    schema = current_user["schema_name"]
    outlet_id = current_user["outlet_id"]
    async for db in get_tenant_db(schema):
        return await expenses_service.list_cash_register(
            db, schema, outlet_id, date_filter
        )