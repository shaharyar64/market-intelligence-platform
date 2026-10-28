import os
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

os.environ["DEBUG"] = "false"

from gateway.app.core import auth
from shared.exceptions import UnauthorizedException


@pytest.fixture
def cognito_token_factory(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    issuer = "https://cognito-idp.us-east-1.amazonaws.com/test-pool"

    monkeypatch.setattr(auth.settings, "AWS_REGION", "us-east-1")
    monkeypatch.setattr(auth.settings, "COGNITO_USER_POOL_ID", "test-pool")
    monkeypatch.setattr(auth.settings, "COGNITO_CLIENT_ID", "test-client")
    monkeypatch.setattr(
        auth._jwks_client,
        "get_signing_key_from_jwt",
        lambda _token: SimpleNamespace(key=public_key),
    )

    def make_token(*, issued_in_seconds: int) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "iss": issuer,
                "sub": "user-1",
                "username": "user-1",
                "client_id": "test-client",
                "token_use": "access",
                "iat": now + issued_in_seconds,
                "exp": now + 3600,
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

    return make_token


def test_accepts_access_token_with_twenty_seconds_of_clock_skew(cognito_token_factory):
    token = cognito_token_factory(issued_in_seconds=20)

    assert auth.verify_jwt(token)["sub"] == "user-1"


def test_rejects_access_token_beyond_clock_skew_allowance(cognito_token_factory):
    token = cognito_token_factory(issued_in_seconds=31)

    with pytest.raises(UnauthorizedException):
        auth.verify_jwt(token)
