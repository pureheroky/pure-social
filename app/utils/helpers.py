# services/auth/helpers.py
import os
from fastapi import Response
from core.config import get_settings

settings = get_settings()


def _cookie_policy() -> dict:
    """
    Dev (ENV != 'production'):   SameSite=Lax,  Secure=False
    Prod (ENV == 'production'):  SameSite=None, Secure=True
    """
    is_prod = os.getenv("ENV") == "production"
    return {
        "secure": True if is_prod else False,
        "samesite": "none" if is_prod else "lax",  # 'none'|'lax'|'strict'
        "path": "/",
    }


def set_auth_cookies(resp: Response, access_token: str, refresh_token: str) -> None:
    policy = _cookie_policy()
    resp.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=policy["secure"],
        samesite=policy["samesite"],
        max_age=settings.ACCESS_TOKEN_TTL,
        path=policy["path"],
    )
    resp.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=policy["secure"],
        samesite=policy["samesite"],
        max_age=settings.REFRESH_TOKEN_TTL,
        path=policy["path"],
    )


def clear_auth_cookies(resp: Response) -> None:
    policy = _cookie_policy()
    resp.delete_cookie("access_token", path=policy["path"])
    resp.delete_cookie("refresh_token", path=policy["path"])
