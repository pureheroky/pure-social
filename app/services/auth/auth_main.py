from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from .routers import auth as auth_router
from .handlers import error_handlers
app = FastAPI(title="Auth api", version="v1")

app.add_exception_handler(HTTPException, error_handlers.http_exception_handler)
app.add_exception_handler(RequestValidationError, error_handlers.http_validation_handler)
app.add_exception_handler(Exception, error_handlers.http_global_handler)


app.include_router(auth_router.router, prefix="/v1/auth", tags=["auth"])
