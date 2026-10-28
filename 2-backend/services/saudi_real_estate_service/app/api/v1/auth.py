from fastapi import APIRouter, Depends, status
from services.saudi_real_estate_service.app.services.cognito import CognitoService
from services.saudi_real_estate_service.app.api.deps import get_cognito_service
from services.saudi_real_estate_service.app.models.schemas import (
    LoginRequest,
    SetPasswordRequest,
    TokenResponse,
    NewPasswordRequiredResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse | NewPasswordRequiredResponse,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticate user with email and password. Returns tokens with role or password change requirement."
)
async def login(
    credentials: LoginRequest,
    cognito: CognitoService = Depends(get_cognito_service)
):
    response = cognito.authenticate_user(credentials.email, credentials.password)

    # Case 1: First-time login, requires password update
    if response.get('ChallengeName') == 'NEW_PASSWORD_REQUIRED':
        return NewPasswordRequiredResponse(
            session=response['Session'],
            password_updated=False
        )

    # Case 2: Login successful with permanent password
    role = cognito.get_user_role(credentials.email)
    auth_result = response['AuthenticationResult']

    return TokenResponse(
        access_token=auth_result['AccessToken'],
        id_token=auth_result['IdToken'],
        refresh_token=auth_result['RefreshToken'],
        expires_in=auth_result.get('ExpiresIn', 3600),
        role=role,
        password_updated=True
    )


@router.post(
    "/set-password",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Set new password",
    description="Set new password after first login with temporary password"
)
async def set_password(
    request: SetPasswordRequest,
    cognito: CognitoService = Depends(get_cognito_service)
):
    response = cognito.respond_to_new_password_challenge(
        request.email,
        request.session,
        request.new_password
    )

    role = cognito.get_user_role(request.email)
    auth_result = response['AuthenticationResult']

    return TokenResponse(
        access_token=auth_result['AccessToken'],
        id_token=auth_result['IdToken'],
        refresh_token=auth_result['RefreshToken'],
        expires_in=auth_result.get('ExpiresIn', 3600),
        role=role,
        password_updated=True 
    )
