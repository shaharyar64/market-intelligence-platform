from fastapi import Response

from gateway.app.core.config import get_settings

REFRESH_TOKEN_COOKIE = "refresh_token"
REFRESH_USERNAME_COOKIE = "refresh_username"
AUTH_COOKIE_PATH = "/auth"


def _cookie_options() -> dict:
    settings = get_settings()
    return {
        "httponly": True,
        "secure": settings.auth_cookie_secure,
        "samesite": "lax",
        "path": AUTH_COOKIE_PATH,
        "max_age": settings.AUTH_COOKIE_MAX_AGE,
    }


def set_refresh_cookies(
    response: Response,
    refresh_token: str | None,
    username: str,
) -> None:
    if not refresh_token:
        return

    options = _cookie_options()
    response.set_cookie(REFRESH_TOKEN_COOKIE, refresh_token, **options)
    response.set_cookie(REFRESH_USERNAME_COOKIE, username, **options)


def clear_refresh_cookies(response: Response) -> None:
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path=AUTH_COOKIE_PATH)
    response.delete_cookie(REFRESH_USERNAME_COOKIE, path=AUTH_COOKIE_PATH)
