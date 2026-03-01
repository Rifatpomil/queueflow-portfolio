"""Admin service – CRUD for tenants, locations, services, counters, channels, users."""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import TokenPayload, hash_password
from app.models.audit_log import AuditLog
from app.models.channel import Channel
from app.models.counter import Counter
from app.models.location import Location
from app.models.service import Service
from app.models.tenant import Tenant
from app.models.user import Role, User, UserRole
from app.repositories.base_repo import BaseRepository
from app.schemas.channel import ChannelCreate, ChannelUpdate
from app.schemas.counter import CounterCreate, CounterUpdate
from app.schemas.location import LocationCreate, LocationUpdate
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.schemas.user import UserCreate, UserUpdate, RoleAssignment

logger = get_logger(__name__)


def _require_admin(actor: TokenPayload) -> None:
    if not actor.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires admin role",
        )


def _require_manager(actor: TokenPayload) -> None:
    if not actor.has_role("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires admin or manager role",
        )


class TenantRepo(BaseRepository[Tenant]):
    model = Tenant


class LocationRepo(BaseRepository[Location]):
    model = Location


class ServiceRepo(BaseRepository[Service]):
    model = Service


class CounterRepo(BaseRepository[Counter]):
    model = Counter


class ChannelRepo(BaseRepository[Channel]):
    model = Channel


class UserRepo(BaseRepository[User]):
    model = User


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._tenants = TenantRepo(session)
        self._locations = LocationRepo(session)
        self._services = ServiceRepo(session)
        self._counters = CounterRepo(session)
        self._channels = ChannelRepo(session)
        self._users = UserRepo(session)

    # ── Audit helpers ──────────────────────────────────────────────────────────
    async def _audit(
        self,
        actor: TokenPayload,
        action: str,
        obj_type: str,
        obj_id: str,
        before: dict | None = None,
        after: dict | None = None,
    ) -> None:
        log = AuditLog(
            tenant_id=UUID(actor.tenant_id) if actor.tenant_id else None,
            actor_user_id=actor.user_id,
            action=action,
            object_type=obj_type,
            object_id=obj_id,
            before_json=before,
            after_json=after,
        )
        self.session.add(log)

    # ── Tenants ────────────────────────────────────────────────────────────────
    async def create_tenant(self, data: TenantCreate, actor: TokenPayload) -> Tenant:
        _require_admin(actor)
        tenant = await self._tenants.create(name=data.name, slug=data.slug)
        await self._audit(actor, "create", "Tenant", str(tenant.id), after=data.model_dump())
        await self.session.commit()
        return tenant

    async def list_tenants(self, actor: TokenPayload) -> list[Tenant]:
        _require_admin(actor)
        return await self._tenants.list()

    async def update_tenant(
        self, tenant_id: UUID, data: TenantUpdate, actor: TokenPayload
    ) -> Tenant:
        _require_admin(actor)
        tenant = await self._tenants.get_or_404(tenant_id)
        before = {"name": tenant.name, "active": tenant.active}
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        tenant = await self._tenants.update(tenant, **updates)
        await self._audit(actor, "update", "Tenant", str(tenant.id), before=before)
        await self.session.commit()
        return tenant

    # ── Locations ──────────────────────────────────────────────────────────────
    async def create_location(self, data: LocationCreate, actor: TokenPayload) -> Location:
        _require_manager(actor)
        loc = await self._locations.create(**data.model_dump())
        await self._audit(actor, "create", "Location", str(loc.id), after=data.model_dump())
        await self.session.commit()
        return loc

    async def list_locations(self, tenant_id: UUID, actor: TokenPayload) -> list[Location]:
        return await self._locations.list(Location.tenant_id == tenant_id)

    async def update_location(
        self, location_id: UUID, data: LocationUpdate, actor: TokenPayload
    ) -> Location:
        _require_manager(actor)
        loc = await self._locations.get_or_404(location_id)
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        loc = await self._locations.update(loc, **updates)
        await self.session.commit()
        return loc

    # ── Services ────────────────────────────────────────────────────────────────
    async def create_service(self, data: ServiceCreate, actor: TokenPayload) -> Service:
        _require_manager(actor)
        svc = await self._services.create(**data.model_dump())
        await self.session.commit()
        return svc

    async def list_services(self, tenant_id: UUID, actor: TokenPayload) -> list[Service]:
        return await self._services.list(Service.tenant_id == tenant_id)

    async def update_service(
        self, service_id: UUID, data: ServiceUpdate, actor: TokenPayload
    ) -> Service:
        _require_manager(actor)
        svc = await self._services.get_or_404(service_id)
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        svc = await self._services.update(svc, **updates)
        await self.session.commit()
        return svc

    # ── Counters ────────────────────────────────────────────────────────────────
    async def create_counter(self, data: CounterCreate, actor: TokenPayload) -> Counter:
        _require_manager(actor)
        counter = await self._counters.create(**data.model_dump())
        await self.session.commit()
        return counter

    async def list_counters(self, location_id: UUID, actor: TokenPayload) -> list[Counter]:
        return await self._counters.list(Counter.location_id == location_id)

    async def update_counter(
        self, counter_id: UUID, data: CounterUpdate, actor: TokenPayload
    ) -> Counter:
        _require_manager(actor)
        counter = await self._counters.get_or_404(counter_id)
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        counter = await self._counters.update(counter, **updates)
        await self.session.commit()
        return counter

    # ── Channels ────────────────────────────────────────────────────────────────
    async def create_channel(self, data: ChannelCreate, actor: TokenPayload) -> Channel:
        _require_manager(actor)
        ch = await self._channels.create(**data.model_dump())
        await self.session.commit()
        return ch

    async def list_channels(self, tenant_id: UUID, actor: TokenPayload) -> list[Channel]:
        return await self._channels.list(Channel.tenant_id == tenant_id)

    # ── Users ──────────────────────────────────────────────────────────────────
    async def create_user(self, data: UserCreate, actor: TokenPayload) -> User:
        _require_admin(actor)
        hashed = hash_password(data.password) if data.password else None
        user = await self._users.create(
            tenant_id=data.tenant_id,
            email=str(data.email),
            display_name=data.display_name,
            hashed_password=hashed,
        )
        await self._audit(actor, "create", "User", str(user.id))
        await self.session.commit()
        return user

    async def list_users(self, tenant_id: UUID, actor: TokenPayload) -> list[User]:
        _require_manager(actor)
        return await self._users.list(User.tenant_id == tenant_id)

    async def assign_role(
        self, user_id: UUID, data: RoleAssignment, actor: TokenPayload
    ) -> None:
        _require_admin(actor)
        user_role = UserRole(
            user_id=user_id,
            role_id=data.role_id,
            location_id=data.location_id,
        )
        self.session.add(user_role)
        await self._audit(actor, "assign_role", "User", str(user_id))
        await self.session.commit()
