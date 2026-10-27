import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.redact import redact

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Custom application exception with an HTTP status code, error code, and message."""
    def __init__(self, status_code: int, code: str, message: str, details: dict = None):
        self.status_code = status_code
        self.code = code
        self.message = redact(message)
        self.details = details or {}
        super().__init__(self.message)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handler for custom application exceptions."""
    err_body = {"code": exc.code, "message": redact(exc.message)}
    if exc.details:
        err_body.update(exc.details)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": err_body},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler for Pydantic input validation failures."""
    errors = exc.errors()
    if errors:
        first_err = errors[0]
        field_loc = " -> ".join(str(loc) for loc in first_err.get("loc", []) if loc != "body")
        msg = first_err.get("msg", "Validation error")
        message = f"{field_loc}: {msg}" if field_loc else msg
    else:
        message = "Validation error"

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": "VALIDATION_ERROR", "message": message}},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handler for standard Starlette/FastAPI HTTP exceptions."""
    # Check if detail is already a dict with code and message
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        code = exc.detail["code"]
        message = exc.detail["message"]
    else:
        # Default code mapped by status code
        status_code_map = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
        }
        code = status_code_map.get(exc.status_code, "HTTP_ERROR")
        message = redact(str(exc.detail)) if exc.detail else "An HTTP error occurred"

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message}},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unexpected unhandled exceptions (500). Does not leak internal trace."""
    logger.exception("Unhandled server exception on %s %s: %s", request.method, request.url.path, redact(str(exc)))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "An unexpected internal error occurred."}},
    )
