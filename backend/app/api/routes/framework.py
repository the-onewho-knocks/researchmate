"""backend/app/api/routes/framework.py"""
from fastapi import APIRouter, Depends

from app.api.deps import get_services

router = APIRouter(prefix="/framework", tags=["framework"])


@router.get("")
async def get_framework(svc=Depends(get_services)):
    """The checklist for the UI. Rule parameters stay on the server."""
    fw = svc.framework
    return {
        "version": fw.version,
        "components": [
            {
                "key": c.key,
                "name": c.name,
                "acronym": c.acronym,
                "criteria": [
                    {"id": k.id, "name": k.name, "tier": k.tier, "hint": k.hint} for k in c.criteria
                ],
            }
            for c in fw.components
        ],
    }
