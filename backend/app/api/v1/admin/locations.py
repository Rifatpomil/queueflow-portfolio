from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.core.security import TokenPayload
from app.schemas.location import LocationCreate, LocationRead, LocationUpdate
from app.services.admin_service import AdminService

router = APIRouter(prefix="/locations", tags=["admin-locations"])


@router.post("", response_model=LocationRead, status_code=201)
async def create_location(
    body: LocationCreate,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> LocationRead:
    svc = AdminService(db)
    loc = await svc.create_location(body, actor)
    return LocationRead.model_validate(loc)


@router.get("", response_model=list[LocationRead])
async def list_locations(
    tenant_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> list[LocationRead]:
    svc = AdminService(db)
    locs = await svc.list_locations(tenant_id, actor)
    return [LocationRead.model_validate(l) for l in locs]


@router.patch("/{location_id}", response_model=LocationRead)
async def update_location(
    location_id: UUID,
    body: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> LocationRead:
    svc = AdminService(db)
    loc = await svc.update_location(location_id, body, actor)
    return LocationRead.model_validate(loc)
