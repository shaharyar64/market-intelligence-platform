from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from services.real_estate_service.app.core.security import verify_cognito_token
from services.real_estate_service.app.services.cognito import CognitoService
from services.real_estate_service.app.utils.exceptions import ForbiddenException


security = HTTPBearer()


def get_cognito_service() -> CognitoService:
    """Dependency to get CognitoService instance"""
    return CognitoService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    cognito: CognitoService = Depends(get_cognito_service)
) -> dict:
    token = credentials.credentials
    user_info = verify_cognito_token(token)

    # Use email, cognito username, or sub as fallback
    username = user_info.get('email') or user_info.get('cognito:username') or user_info.get('sub')
    
    if not username:
        raise HTTPException(status_code=400, detail="Cannot determine username from token")

    # Save it in user_info so all endpoints can safely access it
    user_info['username'] = username

    # Get role
    role = cognito.get_user_role(username)
    user_info['role'] = role
    
    return user_info



async def get_current_active_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Dependency to get current active user"""
    return current_user


async def require_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependency to require admin role
    Raises ForbiddenException if user is not admin
    """
    if current_user.get('role') != 'admin':
        raise ForbiddenException("Admin access required")
    return current_user