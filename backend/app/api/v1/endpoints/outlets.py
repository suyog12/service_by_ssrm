from fastapi import APIRouter, Depends, Query
from uuid import UUID

from app.core.dependencies import get_db, require_feature
from app.schemas.outlet import OutletCreate, OutletUpdate, OutletResponse
from app.services import outlet_service

router = APIRouter(prefix="/outlets", tags=["outlets"])


@router.post("", status_code=201, response_model=OutletResponse)
async def create_outlet(
    data: OutletCreate,
    db=Depends(get_db),
    current_user=Depends(require_feature("outlets.manage", "edit")),
):
    return await outlet_service.create_outlet(
        db, current_user["schema_name"], data.model_dump()
    )


@router.get("", response_model=list[OutletResponse])
async def list_outlets(
    active_only: bool = Query(False),
    db=Depends(get_db),
    current_user=Depends(require_feature("outlets.view", "view")),
):
    return await outlet_service.list_outlets(
        db, current_user["schema_name"], active_only
    )


@router.get("/{outlet_id}", response_model=OutletResponse)
async def get_outlet(
    outlet_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_feature("outlets.view", "view")),
):
    return await outlet_service.get_outlet(
        db, current_user["schema_name"], outlet_id
    )


@router.patch("/{outlet_id}", response_model=OutletResponse)
async def update_outlet(
    outlet_id: UUID,
    data: OutletUpdate,
    db=Depends(get_db),
    current_user=Depends(require_feature("outlets.manage", "edit")),
):
    return await outlet_service.update_outlet(
        db, current_user["schema_name"], outlet_id,
        data.model_dump(exclude_none=True)
    )