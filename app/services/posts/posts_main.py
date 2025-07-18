from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from middlewares.bearer_middleware import BearerCheckMiddleware
from utils import error_handlers
from .routers import post as post_router

app = FastAPI(title="Posts api", version="v1")
app.add_middleware(BearerCheckMiddleware)

app.add_exception_handler(HTTPException, error_handlers.http_exception_handler)
app.add_exception_handler(
    RequestValidationError, error_handlers.http_validation_handler
)
app.add_exception_handler(Exception, error_handlers.http_global_handler)

app.include_router(post_router.router, prefix="/v1/post", tags=["post"])