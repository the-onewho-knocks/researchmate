"""backend/app/api/routes/evaluations.py"""
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app.api.deps import get_services
from app.core.errors import DocumentNotFoundError
from app.schemas.report import EvaluationReport
from app.schemas.upload import EvaluationRequest
from app.services.cache.result_cache import file_sha256
from app.services.orchestrator.pipeline import evaluate_file

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("", response_model=EvaluationReport)
async def create_evaluation(req: EvaluationRequest, svc=Depends(get_services)):
    path, file_type = svc.storage.path_for(req.document_id)
    s = svc.settings

    key = svc.cache.make_key(
        file_sha256(path),
        svc.framework.version,
        s.prompt_version,
        s.gemini_model if svc.llm.available else "no-llm",
        req.coach,
        svc.roles.available,
    )

    cached = svc.cache.get(key)
    if cached:
        report = EvaluationReport(**cached)
        report.cached = True
    else:
        report = await run_in_threadpool(
            evaluate_file, path, file_type, svc, coach=req.coach, document_id=req.document_id
        )
        svc.cache.set(key, report.model_dump())

    report.document_id = req.document_id
    svc.cache.save_report(req.document_id, report.model_dump())
    return report


@router.get("/{document_id}", response_model=EvaluationReport)
async def get_evaluation(document_id: str, svc=Depends(get_services)):
    data = svc.cache.load_report(document_id)
    if not data:
        raise DocumentNotFoundError("No evaluation found for this document (it may have expired).")
    return EvaluationReport(**data)