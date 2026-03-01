from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.core.security import TokenPayload
from app.schemas.counter import CounterCreate, CounterRead, CounterUpdate
from app.services.admin_service import AdminService

router = APIRouter(prefix="/counters", tags=["admin-counters"])


@router.post("", response_model=CounterRead, status_code=201)
async def create_counter(
    body: CounterCreate,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> CounterRead:
    svc = AdminService(db)
    counter = await svc.create_counter(body, actor)
    return CounterRead.model_validate(counter)


@router.get("", response_model=list[CounterRead])
async def list_counters(
    location_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> list[CounterRead]:
    svc = AdminService(db)
    counters = await svc.list_counters(location_id, actor)
    return [CounterRead.model_validate(c) for c in counters]


@router.patch("/{counter_id}", response_model=CounterRead)
async def update_counter(
    counter_id: UUID,
    body: CounterUpdate,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> CounterRead:
    svc = AdminService(db)
    counter = await svc.update_counter(counter_id, body, actor)
    return CounterRead.model_validate(counter)
