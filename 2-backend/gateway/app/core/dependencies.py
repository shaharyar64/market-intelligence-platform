from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from gateway.app.core.auth import verify_jwt
from shared.exceptions import UnauthorizedException

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise UnauthorizedException("Missing Authorization header")

    if credentials.scheme.lower() != "bearer":
        raise UnauthorizedException("Invalid auth scheme")

    return verify_jwt(credentials.credentials)
