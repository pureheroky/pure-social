from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from middlewares.bearer_middleware import BearerCheckMiddleware
from .routers import auth as auth_router
from utils import error_handlers, cors

app = FastAPI(title="Auth api", version="v1")
app.add_middleware(BearerCheckMiddleware)

cors.setup_cors(app)

app.add_exception_handler(HTTPException, error_handlers.http_exception_handler)
app.add_exception_handler(
    RequestValidationError, error_handlers.http_validation_handler
)
app.add_exception_handler(Exception, error_handlers.http_global_handler)


app.include_router(auth_router.router, prefix="/v1/auth", tags=["auth"])
