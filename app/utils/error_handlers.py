from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from utils.logger import setup_log
import logging

setup_log("auth")
logger = logging.getLogger(__name__)

async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        logger.error(f"HTTP error at {request.url.path}: {exc.detail} ")
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": "http_error", "details": exc.detail, "path": request.url.path},
        )
    raise exc

async def http_validation_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, RequestValidationError):
        logger.error(f"Validation error at {request.url.path}: {exc.errors()} | body: {exc.body}")
        errors = exc.errors()
        for error in errors:
            ctx = error.get("ctx")
            if ctx and "error" in ctx and isinstance(ctx["error"], Exception):
                ctx["error"] = str(ctx["error"])
        return JSONResponse(
            status_code=422,
            content={"message": "validation_error", "details": errors, "path": request.url.path},
        )
    raise exc

async def http_global_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unexpected error at {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "unexpected_error", "details": "Something went wrong", "path": request.url.path}
    )
