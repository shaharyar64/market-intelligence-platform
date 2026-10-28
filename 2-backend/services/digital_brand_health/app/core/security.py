import hmac
import hashlib
import base64
from typing import Optional
from jose import jwt, JWTError
from fastapi import HTTPException, status
from services.digital_brand_health.app.core.config import get_settings

settings = get_settings()


def calculate_secret_hash(username: str) -> Optional[str]:
    """Calculate SECRET_HASH for Cognito authentication"""
    if not settings.COGNITO_CLIENT_SECRET:
        return None
    
    message = bytes(username + settings.COGNITO_CLIENT_ID, 'utf-8')
    secret = bytes(settings.COGNITO_CLIENT_SECRET, 'utf-8')
    dig = hmac.new(secret, message, hashlib.sha256).digest()
    return base64.b64encode(dig).decode()


def verify_cognito_token(token: str) -> dict:
    """Verify JWT token from Cognito"""
    try:
        import requests
        
        # Get JWT keys from Cognito
        keys_url = f'https://cognito-idp.{settings.AWS_REGION}.amazonaws.com/{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json'
        
        # Decode without verification to get header
        header = jwt.get_unverified_header(token)
        
        # Fetch keys (should be cached in production)
        keys_response = requests.get(keys_url)
        keys = keys_response.json()['keys']
        
        # Find matching key
        key = next((k for k in keys if k['kid'] == header['kid']), None)
        
        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token - key not found"
            )
        
        # Verify and decode token
        payload = jwt.decode(
            token,
            key,
            algorithms=['RS256'],
            audience=settings.COGNITO_CLIENT_ID
        )
        
        return payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}"
        )