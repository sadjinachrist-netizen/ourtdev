"""Routes festival : lecture publique et administration, dans deux fichiers."""

from fastapi import APIRouter

from app.modules.festival.routes_admin import router as admin_router
from app.modules.festival.routes_public import router as public_router

router = APIRouter()
router.include_router(public_router)
router.include_router(admin_router)
