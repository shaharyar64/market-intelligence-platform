from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.trends_real_estate_service.app.core.security import verify_cognito_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    user = verify_cognito_token(credentials.credentials)
    user["username"] = user.get("email") or user.get("cognito:username") or user.get("sub")
    if not user["username"]:
        raise HTTPException(status_code=400, detail="Cannot determine username from token")
    return user
