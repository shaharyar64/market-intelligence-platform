import os
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["DEBUG"] = "false"

from gateway.app.api import auth
from shared.exceptions import register_exception_handlers


class NotAuthorizedException(Exception):
    pass


class FakeCognito:
    class exceptions:
        NotAuthorizedException = NotAuthorizedException

    def __init__(self):
        self.calls = []
        self.reject_refresh = False

    def initiate_auth(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["AuthFlow"] == "REFRESH_TOKEN_AUTH":
            if self.reject_refresh:
                raise NotAuthorizedException()
            return {
                "AuthenticationResult": {
                    "AccessToken": "refreshed-access",
                    "ExpiresIn": 3600,
                    "TokenType": "Bearer",
                }
            }
        return {
            "AuthenticationResult": {
                "AccessToken": "access-token",
                "IdToken": "id-token",
                "RefreshToken": "refresh-token",
                "ExpiresIn": 3600,
                "TokenType": "Bearer",
            }
        }


class FakeResult:
    def fetchone(self):
        return SimpleNamespace(is_active=True)


class FakeConnection:
    async def execute(self, *_args, **_kwargs):
        return FakeResult()


@asynccontextmanager
async def fake_db_conn():
    yield FakeConnection()


def make_client(monkeypatch):
    cognito = FakeCognito()
    monkeypatch.setattr(auth, "get_cognito_client", lambda: cognito)
    monkeypatch.setattr(auth, "get_db_conn", fake_db_conn)
    monkeypatch.setattr(
        auth,
        "verify_jwt",
        lambda _token: {"username": "cognito-user", "sub": "user-1"},
        raising=False,
    )
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(auth.router)
    return TestClient(app), cognito


def test_login_requires_json_body_and_rejects_query_credentials(monkeypatch):
    client, _ = make_client(monkeypatch)

    response = client.post(
        "/auth/login",
        params={"email": "user@example.com", "password": "not-in-a-url"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("endpoint", "query"),
    [
        ("/auth/complete-new-password", {"email": "user@example.com", "new_password": "secret", "session": "s"}),
        ("/auth/forgot-password", {"email": "user@example.com"}),
        ("/auth/reset-password", {"token": "t", "new_password": "secret"}),
        ("/auth/setup-password", {"token": "t", "new_password": "secret"}),
    ],
)
def test_authentication_inputs_are_not_accepted_from_query_strings(
    monkeypatch,
    endpoint,
    query,
):
    client, _ = make_client(monkeypatch)

    response = client.post(endpoint, params=query)

    assert response.status_code == 422


def test_login_sets_http_only_refresh_cookies_without_exposing_tokens(monkeypatch):
    client, _ = make_client(monkeypatch)

    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "secret"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "access-token",
        "expires_in": 3600,
        "token_type": "Bearer",
    }
    cookies = response.headers.get_list("set-cookie")
    assert any(
        "refresh_token=refresh-token" in value
        and "HttpOnly" in value
        and "Path=/auth" in value
        and "SameSite=lax" in value
        for value in cookies
    )
    assert any("refresh_username=cognito-user" in value for value in cookies)


def test_refresh_requires_cookie(monkeypatch):
    client, _ = make_client(monkeypatch)

    response = client.post("/auth/refresh")

    assert response.status_code == 401


def test_refresh_returns_new_access_token(monkeypatch):
    client, cognito = make_client(monkeypatch)
    client.cookies.set("refresh_token", "stored-refresh", path="/auth")
    client.cookies.set("refresh_username", "cognito-user", path="/auth")

    response = client.post("/auth/refresh")

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "refreshed-access",
        "expires_in": 3600,
        "token_type": "Bearer",
    }
    call = cognito.calls[-1]
    assert call["AuthFlow"] == "REFRESH_TOKEN_AUTH"
    assert call["AuthParameters"]["REFRESH_TOKEN"] == "stored-refresh"
    assert call["AuthParameters"]["SECRET_HASH"]


def test_invalid_refresh_expires_auth_cookies(monkeypatch):
    client, cognito = make_client(monkeypatch)
    cognito.reject_refresh = True
    client.cookies.set("refresh_token", "invalid-refresh", path="/auth")
    client.cookies.set("refresh_username", "cognito-user", path="/auth")

    response = client.post("/auth/refresh")

    assert response.status_code == 401
    cookies = response.headers.get_list("set-cookie")
    assert any("refresh_token=" in value and "Max-Age=0" in value for value in cookies)
    assert any("refresh_username=" in value and "Max-Age=0" in value for value in cookies)


def test_logout_expires_auth_cookies(monkeypatch):
    client, _ = make_client(monkeypatch)

    response = client.post("/auth/logout")

    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    assert any("refresh_token=" in value and "Max-Age=0" in value for value in cookies)
    assert any("refresh_username=" in value and "Max-Age=0" in value for value in cookies)


def test_gateway_cors_allows_exact_local_origin_with_credentials():
    from gateway.app.main import app

    client = TestClient(app)
    response = client.options(
        "/auth/me",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
