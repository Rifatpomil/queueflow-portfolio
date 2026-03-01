from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.core.security import TokenPayload
from app.schemas.user import RoleAssignment, UserCreate, UserRead
from app.services.admin_service import AdminService

router = APIRouter(prefix="/users", tags=["admin-users"])


@router.post("", response_model=UserRead, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> UserRead:
    svc = AdminService(db)
    user = await svc.create_user(body, actor)
    return UserRead.model_validate(user)


@router.get("", response_model=list[UserRead])
async def list_users(
    tenant_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> list[UserRead]:
    svc = AdminService(db)
    users = await svc.list_users(tenant_id, actor)
    return [UserRead.model_validate(u) for u in users]


@router.post("/{user_id}/roles", status_code=204)
async def assign_role(
    user_id: UUID,
    body: RoleAssignment,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> None:
    svc = AdminService(db)
    await svc.assign_role(user_id, body, actor)
