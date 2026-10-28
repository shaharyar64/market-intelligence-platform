from fastapi import HTTPException, status


class CognitoException(HTTPException):
    """Base exception for Cognito errors"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


class AuthenticationException(HTTPException):
    """Authentication failed exception"""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )


class UserNotFoundException(HTTPException):
    """User not found exception"""
    def __init__(self, detail: str = "User not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class ForbiddenException(HTTPException):
    """Forbidden access exception"""
    def __init__(self, detail: str = "Access forbidden"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )