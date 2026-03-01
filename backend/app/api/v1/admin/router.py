"""Admin sub-router – aggregates all admin resource routers."""
from fastapi import APIRouter
from app.api.v1.admin import tenants, locations, services_router, counters_router, channels, users

router = APIRouter(prefix="/admin")

router.include_router(tenants.router)
router.include_router(locations.router)
router.include_router(services_router.router)
router.include_router(counters_router.router)
router.include_router(channels.router)
router.include_router(users.router)
