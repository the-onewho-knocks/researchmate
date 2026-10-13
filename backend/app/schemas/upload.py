from pydantic import BaseModel


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    file_type: str
    size_bytes: int


class EvaluationRequest(BaseModel):
    document_id: str
    coach: bool = False