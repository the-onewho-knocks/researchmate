"""backend/app/api/routes/upload.py"""
from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_services
from app.core.errors import FileTooLargeError
from app.schemas.upload import UploadResponse
from app.services.upload.validator import validate_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse)
async def upload(file: UploadFile = File(...), svc=Depends(get_services)):
    max_bytes = svc.settings.max_upload_mb * 1024 * 1024
    buf = bytearray()
    while chunk := await file.read(1024 * 1024):     # stop reading as soon as the limit is hit
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise FileTooLargeError(f"File exceeds the {svc.settings.max_upload_mb} MB limit.")

    data = bytes(buf)
    name = file.filename or ""
    file_type = validate_upload(name, data, max_bytes)
    doc_id = svc.storage.save(data, file_type, name)
    return UploadResponse(document_id=doc_id, filename=name, file_type=file_type, size_bytes=len(data))
