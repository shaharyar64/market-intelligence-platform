from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger("uvicorn.error")


class AppException(Exception):
    """
    Base application exception
    """
    status_code = 500
    message = "Internal server error"
    error_code = "internal_error"

    def __init__(self, message: str | None = None):
        if message:
            self.message = message
        super().__init__(self.message)


class BadRequestException(AppException):
    status_code = 400
    error_code = "bad_request"


class UnauthorizedException(AppException):
    status_code = 401
    error_code = "unauthorized"


class ForbiddenException(AppException):
    status_code = 403
    error_code = "forbidden"


class NotFoundException(AppException):
    status_code = 404
    error_code = "not_found"


class ServiceUnavailableException(AppException):
    status_code = 503
    error_code = "service_unavailable"


# ---------------------------
# FastAPI exception handlers
# ---------------------------

async def app_exception_handler(
    request: Request,
    exc: AppException,
):
    logger.error(
        f"{exc.error_code}: {exc.message} | path={request.url.path}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
        },
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
):
    logger.warning(
        f"http_exception {exc.status_code}: {exc.detail} | path={request.url.path}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_exception",
            "message": exc.detail,
        },
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    logger.warning(
        f"validation_error: {exc.errors()} | path={request.url.path}"
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Invalid request",
            "details": exc.errors(),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)