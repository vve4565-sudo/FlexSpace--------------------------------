from fastapi import APIRouter

from .admin import router as admin_router
from .auth import router as auth_router
from .manager import router as manager_router
from .rooms import router as room_router
from .users import router as user_router

__all__ = [
    "admin_router",
    "auth_router",
    "manager_router",
    "room_router",
    "router",
    "user_router",
]

router = APIRouter(prefix="/api/v1")

router.include_router(auth_router)
router.include_router(user_router)
router.include_router(manager_router)
router.include_router(admin_router)
router.include_router(room_router)
