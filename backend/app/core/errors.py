from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message


class UnsupportedFileError(AppError):
    status_code = 415
    code = "unsupported_file"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"


class CorruptFileError(AppError):
    status_code = 422
    code = "corrupt_file"


class ExtractionError(AppError):
    status_code = 422
    code = "extraction_failed"


class DocumentNotFoundError(AppError):
    status_code = 404
    code = "not_found"


class FrameworkError(Exception):
    """Framework YAML is invalid."""


class LLMError(Exception):
    """LLM call failed after retries."""


class OutputValidationError(Exception):
    """LLM output could not be parsed or validated."""


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message},
        )
