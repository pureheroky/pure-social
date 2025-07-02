from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from utils.gcs_manager import GCSManager
from .routers.middleware import BearerCheckMiddleware
from utils import error_handlers
from .routers import user as user_router


app = FastAPI(title="Users api", version="v1")
app.add_middleware(BearerCheckMiddleware)

app.add_exception_handler(HTTPException, error_handlers.http_exception_handler)
app.add_exception_handler(
    RequestValidationError, error_handlers.http_validation_handler
)
app.add_exception_handler(Exception, error_handlers.http_global_handler)

app.include_router(user_router.router, prefix="/v1/user", tags=["user"])
