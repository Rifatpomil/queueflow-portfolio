from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.core.security import TokenPayload
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate
from app.services.admin_service import AdminService

router = APIRouter(prefix="/services", tags=["admin-services"])


@router.post("", response_model=ServiceRead, status_code=201)
async def create_service(
    body: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> ServiceRead:
    svc = AdminService(db)
    service = await svc.create_service(body, actor)
    return ServiceRead.model_validate(service)


@router.get("", response_model=list[ServiceRead])
async def list_services(
    tenant_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> list[ServiceRead]:
    svc = AdminService(db)
    services = await svc.list_services(tenant_id, actor)
    return [ServiceRead.model_validate(s) for s in services]


@router.patch("/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: UUID,
    body: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> ServiceRead:
    svc = AdminService(db)
    service = await svc.update_service(service_id, body, actor)
    return ServiceRead.model_validate(service)
