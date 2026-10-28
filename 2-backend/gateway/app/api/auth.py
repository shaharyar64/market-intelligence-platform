import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from gateway.app.core.cognito import get_cognito_client
from gateway.app.core.config import get_settings
from gateway.app.utils.cognito import get_secret_hash
from gateway.app.utils.email import send_reset_password_email
from gateway.app.core.dependencies import get_current_user
from gateway.app.core.auth import verify_jwt
from gateway.app.db.session import get_db_conn
from gateway.app.models.auth import (
    CompleteNewPasswordRequest,
    EmailRequest,
    LoginRequest,
    PasswordTokenRequest,
)
from gateway.app.services.auth_tokens import (
    REFRESH_TOKEN_COOKIE,
    REFRESH_USERNAME_COOKIE,
    clear_refresh_cookies,
    set_refresh_cookies,
)
from shared.exceptions import UnauthorizedException
from shared.logger import get_logger
from shared.redis import ensure_redis

router = APIRouter(prefix="/auth", tags=["Auth"])

settings = get_settings()
logger = get_logger("uvicorn.error")


@router.post("/login")
async def login(payload: LoginRequest, response: Response):
    email = str(payload.email).strip().lower()
    password = payload.password.get_secret_value()
    client = get_cognito_client()
    secret_hash = get_secret_hash(
        email,
        settings.COGNITO_CLIENT_ID,
        settings.COGNITO_CLIENT_SECRET,
    )

    try:
        cognito_response = client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=settings.COGNITO_CLIENT_ID,
            AuthParameters={
                "USERNAME": email,
                "PASSWORD": password,
                "SECRET_HASH": secret_hash,
            },
        )

        if cognito_response.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
            return {
                "challenge": "NEW_PASSWORD_REQUIRED",
                "session": cognito_response["Session"],
            }

        # Check if user is active in database
        async with get_db_conn() as conn:
            result = await conn.execute(
                text("SELECT is_active FROM public.users WHERE LOWER(email) = LOWER(:email)"),
                {"email": email},
            )
            row = result.fetchone()
            if not row or not row.is_active:
                raise UnauthorizedException("Account is inactive or not found")

        auth = cognito_response["AuthenticationResult"]
        claims = verify_jwt(auth["AccessToken"])
        set_refresh_cookies(
            response,
            auth.get("RefreshToken"),
            claims["username"],
        )
        return {
            "access_token": auth["AccessToken"],
            "expires_in": auth["ExpiresIn"],
            "token_type": "Bearer",
        }

    except client.exceptions.NotAuthorizedException:
        raise UnauthorizedException("Invalid email or password")


@router.post("/complete-new-password")
async def complete_new_password(payload: CompleteNewPasswordRequest, response: Response):
    email = str(payload.email).strip().lower()
    new_password = payload.new_password.get_secret_value()
    session = payload.session
    client = get_cognito_client()
    secret_hash = get_secret_hash(
        email,
        settings.COGNITO_CLIENT_ID,
        settings.COGNITO_CLIENT_SECRET,
    )

    cognito_response = client.respond_to_auth_challenge(
        ClientId=settings.COGNITO_CLIENT_ID,
        ChallengeName="NEW_PASSWORD_REQUIRED",
        Session=session,
        ChallengeResponses={
            "USERNAME": email,
            "NEW_PASSWORD": new_password,
            "SECRET_HASH": secret_hash,
        },
    )

    auth = cognito_response["AuthenticationResult"]
    claims = verify_jwt(auth["AccessToken"])
    set_refresh_cookies(
        response,
        auth.get("RefreshToken"),
        claims["username"],
    )
    return {
        "access_token": auth["AccessToken"],
        "expires_in": auth["ExpiresIn"],
        "token_type": "Bearer",
    }


@router.post("/refresh")
async def refresh_access_token(request: Request, response: Response):
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    username = request.cookies.get(REFRESH_USERNAME_COOKIE)
    if not refresh_token or not username:
        raise UnauthorizedException("Missing refresh token")

    client = get_cognito_client()
    try:
        cognito_response = client.initiate_auth(
            AuthFlow="REFRESH_TOKEN_AUTH",
            ClientId=settings.COGNITO_CLIENT_ID,
            AuthParameters={
                "REFRESH_TOKEN": refresh_token,
                "SECRET_HASH": get_secret_hash(
                    username,
                    settings.COGNITO_CLIENT_ID,
                    settings.COGNITO_CLIENT_SECRET,
                ),
            },
        )
    except client.exceptions.NotAuthorizedException:
        error_response = JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Invalid refresh token"},
        )
        clear_refresh_cookies(error_response)
        return error_response

    auth = cognito_response["AuthenticationResult"]
    set_refresh_cookies(response, auth.get("RefreshToken"), username)
    return {
        "access_token": auth["AccessToken"],
        "expires_in": auth["ExpiresIn"],
        "token_type": "Bearer",
    }


@router.post("/logout")
async def logout(response: Response):
    clear_refresh_cookies(response)
    return {"message": "Logged out"}


_RESET_TOKEN_TTL = 3600  # 1 hour


@router.post("/forgot-password")
async def forgot_password(payload: EmailRequest):
    email = str(payload.email).strip().lower()
    async with get_db_conn() as conn:
        result = await conn.execute(
            text("SELECT id FROM public.users WHERE LOWER(email) = LOWER(:email)"),
            {"email": email},
        )
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="No account found with this email")

    redis = await ensure_redis()
    if not redis:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    token = str(uuid.uuid4())
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    await redis.setex(f"reset:{token}", _RESET_TOKEN_TTL, email)

    send_reset_password_email(email, reset_link)

    return {"message": "Password reset link sent to your email"}


@router.post("/reset-password")
async def reset_password(payload: PasswordTokenRequest):
    token = payload.token
    new_password = payload.new_password.get_secret_value()
    redis = await ensure_redis()
    if not redis:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    email_bytes = await redis.get(f"reset:{token}")
    if not email_bytes:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    email = email_bytes.decode("utf-8") if isinstance(email_bytes, bytes) else email_bytes

    client = get_cognito_client()
    try:
        client.admin_set_user_password(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=email,
            Password=new_password,
            Permanent=True,
        )
    except client.exceptions.InvalidPasswordException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except client.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")

    await redis.delete(f"reset:{token}")

    return {"message": "Password reset successful"}


@router.post("/setup-password")
async def setup_password(payload: PasswordTokenRequest):
    token = payload.token
    new_password = payload.new_password.get_secret_value()
    redis = await ensure_redis()
    if not redis:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    email_bytes = await redis.get(f"invite:{token}")
    if not email_bytes:
        raise HTTPException(status_code=400, detail="Invalid or expired invite link")

    email = email_bytes.decode("utf-8") if isinstance(email_bytes, bytes) else email_bytes

    client = get_cognito_client()
    try:
        client.admin_set_user_password(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=email,
            Password=new_password,
            Permanent=True,
        )
    except client.exceptions.InvalidPasswordException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except client.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")

    await redis.delete(f"invite:{token}")

    return {"message": "Password set successfully. You can now log in."}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    async with get_db_conn() as conn:
        result = await conn.execute(
            text(
                "SELECT email, full_name, role FROM users WHERE cognito_sub = :sub"
            ),
            {"sub": user["sub"]},
        )
        row = result.fetchone()

    return {
        "email": row.email if row else None,
        "full_name": row.full_name if row else None,
        "role": row.role if row else None,
    }
