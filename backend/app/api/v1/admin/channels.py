from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.core.security import TokenPayload
from app.schemas.channel import ChannelCreate, ChannelRead
from app.services.admin_service import AdminService

router = APIRouter(prefix="/channels", tags=["admin-channels"])


@router.post("", response_model=ChannelRead, status_code=201)
async def create_channel(
    body: ChannelCreate,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> ChannelRead:
    svc = AdminService(db)
    ch = await svc.create_channel(body, actor)
    return ChannelRead.model_validate(ch)


@router.get("", response_model=list[ChannelRead])
async def list_channels(
    tenant_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> list[ChannelRead]:
    svc = AdminService(db)
    channels = await svc.list_channels(tenant_id, actor)
    return [ChannelRead.model_validate(c) for c in channels]
