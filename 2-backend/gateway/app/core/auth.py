import jwt
from jwt import PyJWKClient
from gateway.app.core.config import get_settings
from shared.exceptions import UnauthorizedException
from shared.logger import get_logger

settings = get_settings()
logger = get_logger("uvicorn.error")
JWT_LEEWAY_SECONDS = 30

JWKS_URL = (
    f"https://cognito-idp.{settings.AWS_REGION}.amazonaws.com/"
    f"{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
)

_jwks_client = PyJWKClient(JWKS_URL)


def verify_jwt(token: str) -> dict:
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)

        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            leeway=JWT_LEEWAY_SECONDS,
            issuer=(
                f"https://cognito-idp.{settings.AWS_REGION}.amazonaws.com/"
                f"{settings.COGNITO_USER_POOL_ID}"
            ),
            options={
                "verify_aud": False,   # 🔑 access tokens don’t use aud
            },
        )

        # 🔒 Explicit safety checks
        if decoded.get("token_use") != "access":
            raise UnauthorizedException("Invalid token type")

        if decoded.get("client_id") != settings.COGNITO_CLIENT_ID:
            raise UnauthorizedException("Invalid client_id")

        return decoded

    except UnauthorizedException:
        raise
    except Exception as exc:
        logger.warning("JWT validation failed: %s", type(exc).__name__)
        raise UnauthorizedException("Invalid or expired token")
