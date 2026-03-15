"""V1 API router – aggregates all resource routers."""
from fastapi import APIRouter

from app.api.v1 import ai, analytics, counters, kiosk, signage, tickets
from app.api.v1.admin.router import router as admin_router

router = APIRouter(prefix="/v1")

router.include_router(tickets.router)
router.include_router(kiosk.router)
router.include_router(counters.router)
router.include_router(signage.router)
router.include_router(analytics.router)
router.include_router(ai.router)
router.include_router(admin_router)
