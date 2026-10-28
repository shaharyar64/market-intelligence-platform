from unittest.mock import patch

import pytest
from fastapi import HTTPException


def _verify(claims, client_id="test-client-id"):
    from services.food_intelligence_service.app.core import security

    with patch.object(security, "_get_jwks", return_value=[{"kid": "k1"}]), \
         patch.object(security.jwt, "get_unverified_header", return_value={"kid": "k1"}), \
         patch.object(security.jwt, "decode", return_value=claims), \
         patch.object(security.settings, "COGNITO_CLIENT_ID", client_id):
        return security.verify_cognito_token("token")


def test_access_token_with_matching_client_id_is_accepted(mock_settings):
    claims = {"token_use": "access", "client_id": "test-client-id", "sub": "u1"}

    assert _verify(claims)["sub"] == "u1"


def test_access_token_without_aud_claim_is_accepted(mock_settings):
    claims = {"token_use": "access", "client_id": "test-client-id", "sub": "u1"}

    assert "aud" not in _verify(claims)


def test_access_token_with_wrong_client_id_is_rejected(mock_settings):
    claims = {"token_use": "access", "client_id": "someone-else", "sub": "u1"}

    with pytest.raises(HTTPException) as exc:
        _verify(claims)

    assert exc.value.status_code == 401


def test_id_token_with_matching_audience_is_accepted(mock_settings):
    claims = {"token_use": "id", "aud": "test-client-id", "sub": "u1"}

    assert _verify(claims)["sub"] == "u1"


def test_id_token_with_wrong_audience_is_rejected(mock_settings):
    claims = {"token_use": "id", "aud": "someone-else", "sub": "u1"}

    with pytest.raises(HTTPException) as exc:
        _verify(claims)

    assert exc.value.status_code == 401


def test_token_with_unexpected_token_use_is_rejected(mock_settings):
    claims = {"token_use": "refresh", "sub": "u1"}

    with pytest.raises(HTTPException) as exc:
        _verify(claims)

    assert exc.value.status_code == 401


def test_decode_is_called_with_issuer_and_audience_verification_disabled(mock_settings):
    from services.food_intelligence_service.app.core import security

    claims = {"token_use": "access", "client_id": "test-client-id"}
    with patch.object(security, "_get_jwks", return_value=[{"kid": "k1"}]), \
         patch.object(security.jwt, "get_unverified_header", return_value={"kid": "k1"}), \
         patch.object(security.jwt, "decode", return_value=claims) as mock_decode, \
         patch.object(security.settings, "COGNITO_CLIENT_ID", "test-client-id"):
        security.verify_cognito_token("token")

    kwargs = mock_decode.call_args.kwargs
    assert kwargs["options"]["verify_aud"] is False
    assert "cognito-idp" in kwargs["issuer"]
