from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer

from .api_v1 import router as v1_router

__all__ = ["router", "index_router"]

swagger_tracker = HTTPBearer(auto_error=False)

router = APIRouter()
# swagger_router = APIRouter(dependencies=[Depends(swagger_tracker)])

router.include_router(v1_router)
