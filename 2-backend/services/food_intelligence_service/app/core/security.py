import requests
from jose import jwt, JWTError
from fastapi import HTTPException, status
from services.food_intelligence_service.app.core.config import get_settings

settings = get_settings()

# Cache the Cognito JWKS across requests (keys rotate rarely).
_JWKS_CACHE: dict | None = None


def _get_jwks() -> list[dict]:
    global _JWKS_CACHE
    if _JWKS_CACHE is None:
        url = (
            f"https://cognito-idp.{settings.AWS_REGION}.amazonaws.com/"
            f"{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        )
        _JWKS_CACHE = requests.get(url, timeout=10).json()["keys"]
    return _JWKS_CACHE


def _issuer() -> str:
    return (
        f"https://cognito-idp.{settings.AWS_REGION}.amazonaws.com/"
        f"{settings.COGNITO_USER_POOL_ID}"
    )


def verify_cognito_token(token: str) -> dict:
    """Verify a Cognito JWT. The gateway already enforces service entitlement;
    here we only confirm the caller presents a valid token.

    Accepts both Cognito token types. Access tokens carry no `aud` claim and
    identify the app via `client_id`; ID tokens carry `aud`. Audience is
    therefore checked per token type rather than by jwt.decode, matching the
    gateway's own verification in gateway/app/core/auth.py.
    """
    try:
        header = jwt.get_unverified_header(token)
        key = next((k for k in _get_jwks() if k["kid"] == header["kid"]), None)
        if not key:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token - key not found")
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=_issuer(),
            options={"verify_aud": False},
        )
        token_use = claims.get("token_use")
        if token_use == "access":
            if claims.get("client_id") != settings.COGNITO_CLIENT_ID:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token - client_id mismatch")
        elif token_use == "id":
            if claims.get("aud") != settings.COGNITO_CLIENT_ID:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token - audience mismatch")
        else:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token - unexpected token_use")
        return claims
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid or expired token: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token verification failed: {e}")
