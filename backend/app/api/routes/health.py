"""backend/app/api/routes/health.py"""
from fastapi import APIRouter, Depends

from app.api.deps import get_services

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health(svc=Depends(get_services)):
    return {
        "status": "ok",
        "llm_available": svc.llm.available,
        "ml_available": svc.roles.available,
        "ml_calibrated": svc.roles.clf is not None,
        "framework_version": svc.framework.version,
    }