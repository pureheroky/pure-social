from fastapi import Request
from core.security import decode_token
from starlette.middleware.base import BaseHTTPMiddleware
from utils.logger import setup_log
from fastapi.responses import JSONResponse
import jwt


class BearerCheckMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.logger = setup_log("middleware", __name__)
        print(f"self.logger.name: {self.logger.name}")
        print(f"self.logger.handlers: {self.logger.handlers}")
        print(f"self.logger.propagate: {self.logger.propagate}")

    async def dispatch(self, request: Request, call_next):
        self.logger.debug(
            f"self.logger name: {self.logger.name}, handlers: {self.logger.handlers}"
        )
        public_paths = [
            "/v1/auth/login",
            "/v1/auth/register",
            "/v1/auth/token/refresh",
        ]

        if request.url.path in public_paths:
            self.logger.debug(
                f"Skipping auth check for public path: {request.url.path}"
            )
            response = await call_next(request)
            client_host = request.client.host if request.client else "unknown"
            self.logger.info(f"Request to: {request.url.path} from {client_host}")
            return response

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
            request.state.user_email = payload["sub"]
        except jwt.ExpiredSignatureError:
            self.logger.error("Token has expired")
            return JSONResponse(
                status_code=401, content={"detail": "Token has expired"}
            )
        except jwt.InvalidSignatureError:
            self.logger.error("Invalid token signature")
            return JSONResponse(
                status_code=401, content={"detail": "Invalid token signature"}
            )
        except Exception as e:
            self.logger.error(f"Token decode error: {str(e)}")
            return JSONResponse(
                status_code=401, content={"detail": f"Bad token: {str(e)}"}
            )

        response = await call_next(request)
        client_host = request.client.host if request.client else "unknown"
        self.logger.info(f"Request to: {request.url.path} from {client_host}")
        return response
