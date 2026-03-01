from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.core.security import TokenPayload
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate
from app.services.admin_service import AdminService

router = APIRouter(prefix="/tenants", tags=["admin-tenants"])


@router.post("", response_model=TenantRead, status_code=201)
async def create_tenant(
    body: TenantCreate,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> TenantRead:
    svc = AdminService(db)
    tenant = await svc.create_tenant(body, actor)
    return TenantRead.model_validate(tenant)


@router.get("", response_model=list[TenantRead])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> list[TenantRead]:
    svc = AdminService(db)
    tenants = await svc.list_tenants(actor)
    return [TenantRead.model_validate(t) for t in tenants]


@router.patch("/{tenant_id}", response_model=TenantRead)
async def update_tenant(
    tenant_id: UUID,
    body: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> TenantRead:
    svc = AdminService(db)
    tenant = await svc.update_tenant(tenant_id, body, actor)
    return TenantRead.model_validate(tenant)
