from fastapi import HTTPException, Request
from core.security import decode_token
from starlette.middleware.base import BaseHTTPMiddleware
from utils.logger import setup_log
import logging
from fastapi.responses import JSONResponse
import jwt

setup_log("users")
logger = logging.getLogger(__name__)


class BearerCheckMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing token"})

        token = auth_header[len("Bearer ") :]

        try:
            payload = decode_token(str(token))
            if "sub" not in payload:
                return JSONResponse(
                    status_code=401, content={"detail": "Provided token is invalid"}
                )
        except jwt.ExpiredSignatureError:
            logger.error("Token has expired")
            return JSONResponse(
                status_code=401, content={"detail": "Token has expired"}
            )
        except jwt.InvalidSignatureError:
            logger.error("Invalid token signature")
            return JSONResponse(
                status_code=401, content={"detail": "Invalid token signature"}
            )
        except Exception as e:
            logger.error(f"Token decode error: {str(e)}")
            return JSONResponse(
                status_code=401, content={"detail": f"Bad token: {str(e)}"}
            )

        response = await call_next(request)
        client_host = request.client.host if request.client else "unknown"
        logger.info(f"Request to: {request.url.path} from {client_host}")
        return response
