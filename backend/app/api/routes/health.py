"""backend/app/api/routes/health.py"""
from fastapi import APIRouter, Depends

from app.api.deps import get_services

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health(svc=Depends(get_services)):
    return {
        "status": "ok",
        "llm_available": svc.llm.available,
        "gemini_available": svc.llm.gemini_available,
        "local_available": svc.llm.local_available,
        "local_model": svc.llm.local.model if svc.llm.local else "",
        "gemini_cooling_down": svc.llm.quota.cooling_down(),
        "gemini_calls_left_today": svc.llm.quota.remaining_calls(),
        "ml_available": svc.roles.available,
        "ml_calibrated": svc.roles.clf is not None,
        "framework_version": svc.framework.version,
    }
